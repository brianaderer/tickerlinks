import logging
from datetime import datetime, timedelta, timezone

from app.extensions import celery
from app.signals.engine import run_analysis
from app.sse import sse_publish
from app.tasks.runtime import acquire_lock, release_lock, mark_heartbeat, get_redis

logger = logging.getLogger(__name__)

PREDICT_COOLDOWN = 1500  # 25 minutes


def _manual_prediction_payload(pred, symbol: str) -> dict:
    return {
        "id": pred.id,
        "company": symbol,
        "direction": pred.direction,
        "confidence": float(pred.confidence),
        "magnitude": float(pred.magnitude) if pred.magnitude else None,
        "reasoning": pred.reasoning,
        "target_date": pred.target_date.isoformat() if pred.target_date else None,
        "created_at": pred.created_at.isoformat(),
        "signal_count": len(pred.signal_matches),
    }


def _create_manual_fallback_prediction(company_id: int, symbol: str, now: datetime):
    from app.extensions import db
    from app.models import Prediction, SignalMatch

    recent_cutoff = now - timedelta(days=7)
    matches = (
        SignalMatch.query.filter(
            SignalMatch.company_id == company_id,
            SignalMatch.source_at >= recent_cutoff,
        )
        .order_by(SignalMatch.source_at.desc())
        .limit(20)
        .all()
    )
    if not matches:
        return None

    bullish_score = sum(float(m.confidence) for m in matches if m.direction == "bullish")
    bearish_score = sum(float(m.confidence) for m in matches if m.direction == "bearish")
    total = bullish_score + bearish_score
    if total <= 0:
        direction = "bullish"
        confidence = 0.5
    elif bullish_score >= bearish_score:
        direction = "bullish"
        confidence = bullish_score / total
    else:
        direction = "bearish"
        confidence = bearish_score / total

    confidence = max(0.5, min(round(confidence, 3), 0.85))
    signal_names = []
    seen = set()
    for m in matches:
        signal_name = getattr(getattr(m, "signal", None), "name", None) or "Unknown signal"
        if signal_name in seen:
            continue
        seen.add(signal_name)
        signal_names.append(signal_name)

    reasoning = (
        f"{direction.title()} fallback outlook based on {len(matches)} recent signal matches "
        f"({', '.join(signal_names[:6])}). This fallback was generated because the full "
        f"multi-signal ensemble did not emit a prediction for this manual run."
    )

    pred = Prediction(
        company_id=company_id,
        direction=direction,
        confidence=confidence,
        magnitude=round(min(0.75, max(0.2, abs(confidence - 0.5) * 2)), 3),
        reasoning=reasoning,
        target_date=now + timedelta(days=7),
        created_at=now,
    )
    pred.signal_matches = matches
    db.session.add(pred)
    db.session.commit()
    return pred


@celery.task(name="app.tasks.analyze.run_signal_analysis")
def run_signal_analysis(company_ids: list[int] | None = None):
    lock = acquire_lock("lock:task:run_signal_analysis", ttl_seconds=840)
    if not lock:
        logger.info("Skipping run_signal_analysis — previous run still in progress")
        return {"skipped": True, "reason": "lock_held"}

    try:
        r = get_redis()
        skip_predict = r.get("last_predict_at") is not None

        mode = "signals-only" if skip_predict else "full"
        logger.info("Starting signal analysis task (mode=%s)", mode)
        sse_publish("signals", "analysis_started", {"mode": mode})

        result = run_analysis(company_ids, skip_predict=skip_predict)
        logger.info("Signal analysis complete (%s): %s", mode, result)

        sse_publish("signals", "analysis_complete", {
            "mode": mode,
            "predictions": result.get("strong_predictions", 0) if isinstance(result, dict) else 0,
            "signals": result.get("total_signals", 0) if isinstance(result, dict) else 0,
        })

        if not skip_predict:
            r.setex("last_predict_at", PREDICT_COOLDOWN, "1")

        mark_heartbeat("analysis")
        return result
    finally:
        release_lock("lock:task:run_signal_analysis", lock)


@celery.task(name="app.tasks.analyze.run_company_prediction")
def run_company_prediction(company_id: int):
    from app.models import Company, Prediction

    company = Company.query.get(company_id)
    symbol = company.symbol if company else f"id={company_id}"
    lock_name = f"lock:task:run_company_prediction:{company_id}"
    lock = acquire_lock(lock_name, ttl_seconds=900)
    if not lock:
        logger.info("Skipping manual prediction for %s — previous run still in progress", symbol)
        sse_publish("signals", "analysis_complete", {
            "mode": "manual",
            "symbol": symbol,
            "prediction": None,
            "error": "Prediction already running for this company",
        })
        return {"skipped": True, "reason": "lock_held", "mode": "manual"}

    run_start = datetime.now(timezone.utc)
    started_at = run_start - timedelta(seconds=2)
    logger.info("Running manual prediction for %s", symbol)
    sse_publish("signals", "analysis_started", {"mode": "manual", "symbol": symbol})

    try:
        result = run_analysis(company_ids=[company_id], skip_predict=False)

        pred = (
            Prediction.query.filter(
                Prediction.company_id == company_id,
                Prediction.created_at >= started_at,
            )
            .order_by(Prediction.created_at.desc())
            .first()
        )

        if not pred:
            pred = _create_manual_fallback_prediction(company_id, symbol, datetime.now(timezone.utc))
            if pred:
                logger.info("Used fallback manual prediction for %s", symbol)
            else:
                logger.info("No prediction generated for %s in manual run", symbol)
                sse_publish("signals", "analysis_complete", {
                    "mode": "manual",
                    "symbol": symbol,
                    "prediction": None,
                    "error": "No prediction generated for this company",
                })
                return {
                    "mode": "manual",
                    "total_signals": result.get("total_signals", 0) if isinstance(result, dict) else 0,
                    "skipped": True,
                }

        prediction_data = _manual_prediction_payload(pred, symbol)

        sse_publish("signals", "analysis_complete", {
            "mode": "manual",
            "symbol": symbol,
            "prediction": prediction_data,
        })
        logger.info("Manual prediction complete for %s", symbol)
        mark_heartbeat("analysis")
        return {
            "mode": "manual",
            "prediction_id": pred.id,
            "total_signals": result.get("total_signals", 0) if isinstance(result, dict) else 0,
            "strong_predictions": result.get("strong_predictions", 0) if isinstance(result, dict) else 0,
            "weak_predictions": result.get("weak_predictions", 0) if isinstance(result, dict) else 0,
        }

    except Exception as e:
        logger.exception("Manual prediction failed for %s", symbol)
        sse_publish("signals", "analysis_complete", {
            "mode": "manual",
            "symbol": symbol,
            "prediction": None,
            "error": str(e),
        })
        return {"mode": "manual", "error": str(e)}
    finally:
        release_lock(lock_name, lock)

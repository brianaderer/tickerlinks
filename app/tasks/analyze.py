import logging

from app.extensions import celery
from app.signals.engine import run_analysis
from app.sse import sse_publish
from app.tasks.runtime import acquire_lock, release_lock, mark_heartbeat, get_redis

logger = logging.getLogger(__name__)

PREDICT_COOLDOWN = 1500  # 25 minutes


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
    from datetime import datetime, timedelta, timezone
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

    started_at = datetime.now(timezone.utc) - timedelta(seconds=2)
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

        prediction_data = {
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

import logging
import os

import redis

from app.extensions import celery
from app.signals.engine import run_analysis
from app.sse import sse_publish

logger = logging.getLogger(__name__)

PREDICT_COOLDOWN = 1500  # 25 minutes


def _get_redis():
    url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
    return redis.from_url(url, decode_responses=True)


@celery.task(name="app.tasks.analyze.run_signal_analysis")
def run_signal_analysis(company_ids: list[int] | None = None):
    r = _get_redis()
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

    from app.tasks.trends import generate_trends
    generate_trends.delay()

    if not skip_predict:
        r.setex("last_predict_at", PREDICT_COOLDOWN, "1")

    return result


@celery.task(name="app.tasks.analyze.run_company_prediction")
def run_company_prediction(company_id: int):
    from datetime import datetime, timedelta, timezone
    from app.models import Company, Prediction, SignalMatch
    from app.signals.nodes.gather import gather_node
    from app.signals.nodes.aggregate import aggregate_node
    from app.signals.nodes.predict import predict_node
    from app.signals.nodes.evaluate import evaluate_node
    from app.signals.nodes.output import output_node
    from app.signals.nodes.digest import digest_node

    company = Company.query.get(company_id)
    symbol = company.symbol if company else f"id={company_id}"
    logger.info("Running manual prediction for %s", symbol)
    sse_publish("signals", "analysis_started", {"mode": "manual", "symbol": symbol})

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    matches = SignalMatch.query.filter(
        SignalMatch.company_id == company_id,
        SignalMatch.detected_at >= cutoff,
    ).all()

    if not matches:
        logger.info("No recent signals for %s, skipping prediction", symbol)
        sse_publish("signals", "analysis_complete", {
            "mode": "manual",
            "symbol": symbol,
            "prediction": None,
            "error": "No signals detected for this company",
        })
        return {"total_signals": 0, "skipped": True}

    signals = [
        {
            "signal_name": m.signal.name,
            "signal_type": m.signal.signal_type,
            "company_id": m.company_id,
            "symbol": symbol,
            "direction": m.direction,
            "confidence": float(m.confidence),
            "context": m.context or {},
        }
        for m in matches
    ]

    state = {
        "company_ids": [company_id],
        "price_data": {},
        "news_data": {},
        "fundamentals_data": {},
        "insider_data": {},
        "signals": signals,
        "predictions": [],
        "iteration": 0,
        "max_iterations": 1,
        "confidence_threshold": 0.0,
    }

    state = gather_node(state)

    bullish = [s for s in signals if s["direction"] == "bullish"]
    bearish = [s for s in signals if s["direction"] == "bearish"]
    bullish_score = sum(s["confidence"] for s in bullish)
    bearish_score = sum(s["confidence"] for s in bearish)
    total = bullish_score + bearish_score
    direction = "bullish" if bullish_score >= bearish_score else "bearish"
    confidence = round(max(bullish_score, bearish_score) / total if total else 0.5, 3)

    state["predictions"] = [{
        "company_id": company_id,
        "symbol": symbol,
        "direction": direction,
        "confidence": confidence,
        "bullish_signals": len(bullish),
        "bearish_signals": len(bearish),
        "signal_names": [s["signal_name"] for s in signals],
        "weights_used": {},
    }]

    state = predict_node(state)
    state = evaluate_node(state)
    state = output_node(state)
    state = digest_node(state)

    logger.info("Manual prediction complete for %s", symbol)

    prediction_data = None
    pred = Prediction.query.filter_by(company_id=company_id).order_by(
        Prediction.created_at.desc()
    ).first()
    if pred:
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
    return {
        "total_signals": len(signals),
        "strong_predictions": len(state.get("strong_predictions", [])),
        "mode": "manual",
    }

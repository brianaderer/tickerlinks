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
    from app.models import Company
    company = Company.query.get(company_id)
    symbol = company.symbol if company else f"id={company_id}"
    logger.info("Running manual prediction for %s", symbol)
    sse_publish("signals", "analysis_started", {"mode": "manual", "symbol": symbol})

    result = run_analysis(company_ids=[company_id], skip_predict=False)
    logger.info("Manual prediction complete for %s: %s", symbol, result)

    sse_publish("signals", "analysis_complete", {
        "mode": "manual",
        "symbol": symbol,
        "predictions": result.get("strong_predictions", 0) if isinstance(result, dict) else 0,
    })
    return result

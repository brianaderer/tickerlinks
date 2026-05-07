import logging

from app.extensions import celery
from app.signals.engine import run_analysis
from app.sse import sse_publish

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.analyze.run_signal_analysis")
def run_signal_analysis(company_ids: list[int] | None = None):
    logger.info("Starting signal analysis task")
    sse_publish("signals", "analysis_started", {})
    result = run_analysis(company_ids)
    logger.info("Signal analysis complete: %s", result)

    matches = result.get("signal_matches", []) if isinstance(result, dict) else []
    sse_publish("signals", "analysis_complete", {
        "predictions": result.get("predictions", 0) if isinstance(result, dict) else 0,
        "matches": len(matches) if isinstance(matches, list) else 0,
    })

    from app.tasks.report import generate_report
    generate_report.delay()

    from app.tasks.trends import generate_trends
    generate_trends.delay()

    return result

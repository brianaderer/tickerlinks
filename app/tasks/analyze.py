import logging

from app.extensions import celery
from app.signals.engine import run_analysis

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.analyze.run_signal_analysis")
def run_signal_analysis(company_ids: list[int] | None = None):
    logger.info("Starting signal analysis task")
    result = run_analysis(company_ids)
    logger.info("Signal analysis complete: %s", result)
    return result

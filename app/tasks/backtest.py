import logging

from app.extensions import celery
from app.signals.backtester import run_backtest

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.backtest.run_historical_backtest")
def run_historical_backtest(company_ids: list[int] | None = None):
    logger.info("Starting historical backtest")
    result = run_backtest(company_ids)
    logger.info("Backtest complete: %s", result)
    return result

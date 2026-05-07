import logging

from app.extensions import celery
from app.signals.backtester import get_due_windows, run_window_backtest

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.backtest.check_backtest_windows")
def check_backtest_windows():
    due = get_due_windows()
    if not due:
        logger.info("No backtest windows due")
        return {"windows_processed": 0}

    logger.info("Found %d due backtest windows", len(due))
    results = []
    for window in due:
        result = run_window_backtest(window)
        results.append(result)
        logger.info("Completed window: %s", result["label"])

    return {"windows_processed": len(results), "windows": [r["label"] for r in results]}

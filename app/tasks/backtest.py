import logging

from app.extensions import celery
from app.signals.backtester import get_due_windows, run_window_backtest
from app.sse import sse_publish

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
        sse_publish("backtest", "window_started", {"label": window["label"]})
        result = run_window_backtest(window)
        results.append(result)
        sse_publish("backtest", "window_complete", {
            "label": result["label"],
            "companies_tested": result["companies_tested"],
            "signal_pairs": result["signal_pairs"],
        })
        logger.info("Completed window: %s", result["label"])

    return {"windows_processed": len(results), "windows": [r["label"] for r in results]}

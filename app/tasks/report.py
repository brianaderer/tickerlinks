import logging

from app.extensions import celery
from app.reports.generator import generate_hourly_report
from app.sse import sse_publish
from app.tasks.runtime import acquire_lock, release_lock, mark_heartbeat

logger = logging.getLogger(__name__)


@celery.task(
    name="app.tasks.report.generate_report",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def generate_report():
    lock = acquire_lock("lock:task:generate_report", ttl_seconds=900)
    if not lock:
        logger.info("Skipping generate_report — previous run still in progress")
        return {"skipped": True, "reason": "lock_held"}

    try:
        logger.info("Generating hourly report")
        report = generate_hourly_report()
        logger.info("Report #%d generated: %s", report.id, report.summary[:100] if report.summary else "")
        mark_heartbeat("report")
        sse_publish("reports", "generated", {
            "report_id": report.id,
            "summary": (report.summary[:200] if report.summary else ""),
            "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        })
        return {"report_id": report.id}
    finally:
        release_lock("lock:task:generate_report", lock)

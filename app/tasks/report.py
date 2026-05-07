import logging

from app.extensions import celery
from app.reports.generator import generate_hourly_report
from app.sse import sse_publish

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.report.generate_report")
def generate_report():
    logger.info("Generating hourly report")
    report = generate_hourly_report()
    logger.info("Report #%d generated: %s", report.id, report.summary[:100] if report.summary else "")
    sse_publish("reports", "generated", {
        "report_id": report.id,
        "summary": (report.summary[:200] if report.summary else ""),
    })
    return {"report_id": report.id}

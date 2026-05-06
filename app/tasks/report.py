import logging

from app.extensions import celery
from app.reports.generator import generate_hourly_report

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.report.generate_report")
def generate_report():
    logger.info("Generating hourly report")
    report = generate_hourly_report()
    logger.info("Report #%d generated: %s", report.id, report.summary[:100] if report.summary else "")
    return {"report_id": report.id}

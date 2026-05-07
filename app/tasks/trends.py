import logging

from app.extensions import celery
from app.trends.agent import run_trending_agent
from app.sse import sse_publish

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.trends.generate_trends")
def generate_trends():
    logger.info("Starting trending analysis")
    snapshot = run_trending_agent()
    trend_count = len(snapshot.trends) if snapshot.trends else 0
    logger.info("Trending analysis complete: %d trends", trend_count)
    sse_publish("trends", "updated", {"count": trend_count})
    return {"trend_count": trend_count}

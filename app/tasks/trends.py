import logging

from app.extensions import celery
from app.trends.agent import run_trending_agent
from app.sse import sse_publish
from app.tasks.runtime import acquire_lock, release_lock, mark_heartbeat

logger = logging.getLogger(__name__)


@celery.task(
    name="app.tasks.trends.generate_trends",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 2},
)
def generate_trends():
    lock = acquire_lock("lock:task:generate_trends", ttl_seconds=1200)
    if not lock:
        logger.info("Skipping generate_trends — previous run still in progress")
        return {"skipped": True, "reason": "lock_held"}

    try:
        logger.info("Starting trending analysis")
        snapshot = run_trending_agent()
        trend_count = len(snapshot.trends) if snapshot.trends else 0
        logger.info("Trending analysis complete: %d trends", trend_count)
        mark_heartbeat("trends")
        sse_publish("trends", "updated", {
            "count": trend_count,
            "generated_at": snapshot.generated_at.isoformat() if snapshot.generated_at else None,
        })
        return {"trend_count": trend_count}
    finally:
        release_lock("lock:task:generate_trends", lock)

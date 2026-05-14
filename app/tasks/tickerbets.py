import logging

from app.extensions import celery
from app.sse import sse_publish
from app.tasks.runtime import acquire_lock, mark_heartbeat, release_lock
from app.tickerbets.service import train_and_store_models

logger = logging.getLogger(__name__)


def train_tickerbets_sync():
    run = train_and_store_models()
    mark_heartbeat("tickerbets")
    return {
        "run_id": run.run_id,
        "status": run.status,
        "company_count": run.company_count,
        "sample_count": run.sample_count,
    }


@celery.task(
    name="app.tasks.tickerbets.train_tickerbets",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 2},
)
def train_tickerbets():
    lock = acquire_lock("lock:task:train_tickerbets", ttl_seconds=60 * 60 * 3)
    if not lock:
        logger.info("Skipping train_tickerbets — previous run still in progress")
        return {"skipped": True, "reason": "lock_held"}

    sse_publish("tickerbets", "train_started", {})
    try:
        run = train_and_store_models()
        mark_heartbeat("tickerbets")
        payload = {
            "run_id": run.run_id,
            "status": run.status,
            "company_count": run.company_count,
            "sample_count": run.sample_count,
            "train_count": run.train_count,
            "test_count": run.test_count,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
        sse_publish("tickerbets", "train_complete", payload)
        return payload
    except Exception as exc:
        logger.exception("Tickerbets training failed")
        sse_publish("tickerbets", "train_failed", {"error": str(exc)})
        raise
    finally:
        release_lock("lock:task:train_tickerbets", lock)

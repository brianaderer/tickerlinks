import json
import os
from datetime import datetime, timezone

import redis

_redis_client = None

STREAM_KEY = "sse:events"
STREAM_MAXLEN = 5000


def _get_redis():
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
        _redis_client = redis.from_url(url, decode_responses=True)
    return _redis_client


def sse_publish(channel: str, event: str, data: dict | None = None):
    r = _get_redis()
    entry = {
        "channel": channel,
        "event": event,
        "data": json.dumps(data or {}),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    r.xadd(STREAM_KEY, entry, maxlen=STREAM_MAXLEN)

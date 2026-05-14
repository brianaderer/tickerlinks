import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import redis


LOCK_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
else
  return 0
end
"""


def get_redis():
    url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
    return redis.from_url(url, decode_responses=True)


def acquire_lock(name: str, ttl_seconds: int = 900) -> tuple[Any, str] | None:
    r = get_redis()
    token = uuid4().hex
    ok = r.set(name, token, nx=True, ex=ttl_seconds)
    if not ok:
        return None
    return r, token


def release_lock(name: str, lock: tuple[Any, str] | None):
    if not lock:
        return
    r, token = lock
    try:
        r.eval(LOCK_RELEASE_SCRIPT, 1, name, token)
    except Exception:
        # lock expiry races are acceptable; this is best-effort cleanup
        pass


def mark_heartbeat(name: str) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    r = get_redis()
    r.set(f"heartbeat:{name}:last_success", ts)
    return ts


def get_heartbeat(name: str) -> str | None:
    r = get_redis()
    return r.get(f"heartbeat:{name}:last_success")

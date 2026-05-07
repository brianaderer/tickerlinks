import json
import os
import time

import redis
from flask import Blueprint, Response, request

from app.sse.publisher import STREAM_KEY

bp = Blueprint("sse", __name__)

HEARTBEAT_INTERVAL = 30


@bp.route("/stream")
def stream():
    last_id = request.headers.get("Last-Event-ID", request.args.get("last_id", "$"))

    redis_url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
    r = redis.from_url(redis_url, decode_responses=True)

    def generate():
        read_id = last_id
        last_heartbeat = time.time()

        while True:
            results = r.xread({STREAM_KEY: read_id}, count=50, block=2000)

            if results:
                for _stream_name, entries in results:
                    for entry_id, fields in entries:
                        channel = fields.get("channel", "")
                        event = fields.get("event", "")
                        data = fields.get("data", "{}")
                        ts = fields.get("ts", "")

                        payload = json.loads(data)
                        payload["channel"] = channel
                        payload["event"] = event
                        payload["ts"] = ts

                        yield f"id: {entry_id}\nevent: {channel}:{event}\ndata: {json.dumps(payload)}\n\n"
                        read_id = entry_id

            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                yield f"event: system:heartbeat\ndata: {{\"ts\":\"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\"}}\n\n"
                last_heartbeat = now

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

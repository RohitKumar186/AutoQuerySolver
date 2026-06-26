"""
queue/redis_consumer.py
Worker 5 — Redis queue consumer.

Polls the "approved_fixes" Redis list for fixes approved by Worker 4.
Uses brpop (blocking pop) — sits idle until a fix arrives.
Like a government office token counter — waits for the next number to be called.

Worker 4 pushes to Redis like this:
    redis.lpush("approved_fixes", json.dumps({
        "record_id":    5,
        "table":        "customers",
        "fixed_record": {"name": "Rohit Singh", "phone": "UNKNOWN"},
        "original":     {"id": 5, "name": "Rohit Sin11", "phone": "not-a-phone"},
        "confidence":   0.91,
        "approved_by":  "AUTO",
        "explanation":  "Fixed typo in name.",
        "ts":           "14:30:00"
    }))

Worker 5 picks up with brpop and processes one fix at a time.
"""

import json
import logging
import os
import redis
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("RedisConsumer")

REDIS_HOST  = os.getenv("REDIS_HOST", "redis")
REDIS_PORT  = int(os.getenv("REDIS_PORT", "6379"))
QUEUE_KEY   = "approved_fixes"
TIMEOUT_SEC = 5       # brpop timeout — wakes up every 5s to check if shutting down


def get_redis_client() -> redis.Redis:
    """
    Creates and returns a Redis client.
    Tests connection immediately so we fail fast if Redis is down.
    """
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,    # returns str instead of bytes
        )
        client.ping()
        log.info(f"✅ Redis connected — {REDIS_HOST}:{REDIS_PORT}")
        return client
    except Exception as exc:
        log.error(f"❌ Redis connection failed: {exc}")
        raise


def consume_one(client: redis.Redis) -> dict | None:
    """
    Blocking pop — waits up to TIMEOUT_SEC seconds for a fix.
    Returns the fix payload dict, or None if timeout (no fix arrived).

    brpop returns: ("approved_fixes", '{"record_id": 5, ...}')
    We take index [1] — the actual JSON value.
    """
    try:
        result = client.brpop(QUEUE_KEY, timeout=TIMEOUT_SEC)

        if result is None:
            # Timeout — no fix in queue, that's normal
            return None

        _, raw_json = result
        payload = json.loads(raw_json)
        log.info(
            f"  📬 Fix dequeued — record_id={payload.get('record_id')} "
            f"approved_by={payload.get('approved_by')} "
            f"confidence={payload.get('confidence')}"
        )
        return payload

    except json.JSONDecodeError as exc:
        log.error(f"  ❌ Could not parse Redis payload as JSON: {exc}")
        return None
    except Exception as exc:
        log.error(f"  ❌ Redis consume error: {exc}")
        return None


def queue_length(client: redis.Redis) -> int:
    """Returns how many fixes are currently waiting in the queue."""
    try:
        return client.llen(QUEUE_KEY)
    except Exception:
        return 0
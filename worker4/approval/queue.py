"""
approval/queue.py
Redis Queue — holds fixes that need human approval.
Uses a Redis LIST as a simple FIFO queue.

Queue names:
    watchman:pending   — fixes waiting for human review
    watchman:approved  — approved fixes (ready to apply)
    watchman:rejected  — rejected fixes (discarded)
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("ApprovalQueue")

REDIS_URL       = os.getenv("REDIS_URL", "redis://redis:6379")
QUEUE_PENDING   = "watchman:pending"
QUEUE_APPROVED  = "watchman:approved"
QUEUE_REJECTED  = "watchman:rejected"
QUEUE_ALL_FIXES = "watchman:all_fixes"   # hash: fix_id → full payload (for API lookup)


def _get_redis():
    try:
        import redis
        client = redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        log.info(f"✅ Redis connected — {REDIS_URL}")
        return client
    except Exception as exc:
        log.error(f"❌ Redis connection failed: {exc}")
        return None


class ApprovalQueue:
    """
    Manages the fix approval lifecycle via Redis.

    States:
        pending  → fix is waiting for human decision
        approved → human (or auto) approved; applier.py will write to MySQL
        rejected → human rejected; fix is discarded
    """

    def __init__(self):
        self._r = _get_redis()

    @property
    def available(self) -> bool:
        return self._r is not None

    # ── Push / Pop ────────────────────────────────────────────────────────────

    def push_pending(self, fix_payload: dict) -> bool:
        """
        Add a fix to the pending queue for human review.
        Also stores the full payload in a hash for API lookup by fix_id.
        """
        if not self._r:
            log.error("❌ Redis unavailable — cannot queue fix.")
            return False
        try:
            fix_id  = fix_payload["fix_id"]
            payload = json.dumps(fix_payload)

            # Store full payload for O(1) lookup
            self._r.hset(QUEUE_ALL_FIXES, fix_id, payload)

            # Push to pending list
            self._r.lpush(QUEUE_PENDING, fix_id)

            count = self._r.llen(QUEUE_PENDING)
            log.info(f"  📥 Queued for human review — fix_id={fix_id} (queue depth: {count})")
            return True
        except Exception as exc:
            log.error(f"❌ push_pending error: {exc}")
            return False

    def push_approved(self, fix_id: str, approved_by: str = "auto") -> bool:
        """Move a fix from pending to approved."""
        return self._move(fix_id, to_queue=QUEUE_APPROVED, status="approved", by=approved_by)

    def push_rejected(self, fix_id: str, rejected_by: str, reason: str = "") -> bool:
        """Move a fix from pending to rejected."""
        return self._move(fix_id, to_queue=QUEUE_REJECTED, status="rejected", by=rejected_by, reason=reason)

    def pop_approved(self) -> Optional[dict]:
        """
        Pop the next approved fix for applier.py to process.
        Returns the full payload dict, or None if queue is empty.
        """
        if not self._r:
            return None
        try:
            fix_id = self._r.rpop(QUEUE_APPROVED)
            if not fix_id:
                return None
            payload_str = self._r.hget(QUEUE_ALL_FIXES, fix_id)
            if not payload_str:
                log.warning(f"⚠️  Approved fix_id={fix_id} not found in hash store.")
                return None
            return json.loads(payload_str)
        except Exception as exc:
            log.error(f"❌ pop_approved error: {exc}")
            return None

    # ── Lookup ────────────────────────────────────────────────────────────────

    def get_fix(self, fix_id: str) -> Optional[dict]:
        """Get the full payload for a fix_id."""
        if not self._r:
            return None
        try:
            payload_str = self._r.hget(QUEUE_ALL_FIXES, fix_id)
            return json.loads(payload_str) if payload_str else None
        except Exception as exc:
            log.error(f"❌ get_fix error: {exc}")
            return None

    def list_pending(self) -> list[dict]:
        """Return all fixes currently in the pending queue (for the approval UI)."""
        if not self._r:
            return []
        try:
            fix_ids = self._r.lrange(QUEUE_PENDING, 0, -1)
            fixes   = []
            for fix_id in fix_ids:
                payload_str = self._r.hget(QUEUE_ALL_FIXES, fix_id)
                if payload_str:
                    fixes.append(json.loads(payload_str))
            return fixes
        except Exception as exc:
            log.error(f"❌ list_pending error: {exc}")
            return []

    def pending_count(self) -> int:
        if not self._r:
            return 0
        try:
            return self._r.llen(QUEUE_PENDING)
        except Exception:
            return 0
    
    def push_to_executor(self, full_payload: dict) -> bool:
        """Push approved fix directly to Worker 5 executor queue."""
        if not self._r:
            log.error("❌ Redis unavailable — cannot push to executor.")
            return False
        try:
            self._r.lpush("approved_fixes", json.dumps(full_payload))
            log.info(f"  📤 Fix pushed to Worker 5 — record_id={full_payload.get('record_id')}")
            return True
        except Exception as exc:
            log.error(f"❌ push_to_executor error: {exc}")
            return False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _move(self, fix_id: str, to_queue: str, status: str, by: str, reason: str = "") -> bool:
        if not self._r:
            return False
        try:
            # Remove from pending
            self._r.lrem(QUEUE_PENDING, 0, fix_id)

            # Update payload with decision metadata
            payload_str = self._r.hget(QUEUE_ALL_FIXES, fix_id)
            if payload_str:
                payload = json.loads(payload_str)
                payload["status"]      = status
                payload["decided_by"]  = by
                payload["decided_at"]  = datetime.now(timezone.utc).isoformat()
                payload["reject_reason"] = reason
                self._r.hset(QUEUE_ALL_FIXES, fix_id, json.dumps(payload))

            # Push to destination queue
            self._r.lpush(to_queue, fix_id)
            log.info(f"  ✅ fix_id={fix_id} → {status} (by={by})")
            return True
        except Exception as exc:
            log.error(f"❌ _move error: {exc}")
            return False
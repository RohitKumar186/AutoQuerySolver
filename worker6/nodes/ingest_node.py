"""
worker6/nodes/ingest_node.py
Step 1 — Parse and normalize the incoming event from Kafka.

Worker 6 listens to the same Kafka topic as Workers 2 and 3.
It reads raw Debezium CDC events and enriches them with whatever
Worker 5 execution metadata is available.

If the record has no issues (clean insert), the pipeline is skipped.
"""

import json
import logging

log = logging.getLogger("IngestNode")


def ingest_node(state: dict) -> dict:
    raw = state.get("raw_event", {})

    if not raw:
        log.warning("  ⚠️  Empty raw_event — skipping.")
        return {**state, "skipped": True}

    op     = raw.get("op", "?")
    after  = raw.get("after") or raw.get("record") or {}
    before = raw.get("before")

    if not after:
        log.info("  ⏭️  No 'after' payload (delete event?) — skipping.")
        return {**state, "skipped": True}

    record_id  = after.get("id")
    issues     = raw.get("issues", [])
    fixed      = raw.get("fixed", {})
    original   = raw.get("original", after)
    confidence = raw.get("confidence")
    fix_valid  = raw.get("fix_valid", False)
    approved_by= raw.get("approved_by")
    explanation= raw.get("explanation", "")
    worker     = raw.get("worker", "worker5")
    ts         = raw.get("ts", "")

    # If there are no issues AND no fixed fields, this is a clean record.
    # Still log it to the audit table but mark it accordingly.
    is_fix_event = bool(issues or fixed)

    log.info(
        f"  📥 Ingested — op={op} record_id={record_id} "
        f"is_fix={is_fix_event} confidence={confidence}"
    )

    return {
        **state,
        "op":          op,
        "record_id":   record_id,
        "original":    original,
        "fixed":       fixed,
        "before":      before,
        "issues":      issues,
        "confidence":  confidence,
        "fix_valid":   fix_valid,
        "approved_by": approved_by,
        "explanation": explanation,
        "worker":      worker,
        "ts":          ts,
        "is_fix_event": is_fix_event,
        "skipped":     False,
    }
"""
Worker 4 — The Checker (Validation Agent)
Polls ChromaDB for new fixes saved by Worker 3 (The Doctor).
Runs every fix through 3 validation layers, then either:
  - AUTO-APPROVES  (high confidence + all validations pass) → writes to MySQL
  - HUMAN REVIEW   (low confidence or validation issues)    → Redis queue + Slack/Email alert

Pipeline per fix:
  Step 1 — JSON Schema validation     (shape check)
  Step 2 — Pydantic validation        (type + value check)
  Step 3 — DB dry-run validation      (SQLAlchemy constraint check)
  Step 4 — Confidence threshold check
           ├── HIGH → auto-approve → applier.py → MySQL ✅
           └── LOW  → push to Redis → notify manager → wait for approval

FastAPI server runs in background (port 8000) for the approval UI.
"""

import json
import logging
import os
import threading
import time
import uvicorn
from datetime import datetime, timezone

import chromadb
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("CheckerAgent")

# ── Config ────────────────────────────────────────────────────────────────────
CHROMA_PATH            = os.getenv("CHROMA_PATH",            "/chroma_data")
COLLECTION_NAME        = "doctor_fixes"
POLL_INTERVAL_SECONDS  = int(os.getenv("POLL_INTERVAL",      "10"))
AUTO_APPROVE_THRESHOLD = float(os.getenv("AUTO_APPROVE_THRESHOLD", "0.80"))
API_HOST               = os.getenv("API_HOST",               "0.0.0.0")
API_PORT               = int(os.getenv("API_PORT",           "8000"))

# ── Track which fix_ids we've already processed ───────────────────────────────
# In production swap this for a Redis SET to survive restarts
_processed_ids: set = set()


# ── ChromaDB ──────────────────────────────────────────────────────────────────
def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def fetch_new_fixes() -> list[dict]:
    """
    Pull all fixes from ChromaDB that we haven't processed yet.
    ChromaDB doesn't have a pub/sub — we poll and track seen IDs.
    """
    try:
        collection = get_collection()
        total      = collection.count()

        if total == 0:
            return []

        results = collection.get(
            include=["metadatas", "documents"],
        )

        new_fixes = []
        ids       = results.get("ids", [])
        metas     = results.get("metadatas", [])

        for fix_id, meta in zip(ids, metas):
            if fix_id in _processed_ids:
                continue

            try:
                payload = {
                    "fix_id":       fix_id,
                    "original":     json.loads(meta.get("original", "{}")),
                    "issues":       json.loads(meta.get("issues",   "[]")),
                    "fixed":        json.loads(meta.get("fixed",    "{}")),
                    "fixed_fields": json.loads(meta.get("fixed",    "{}")),
                    "explanation":  meta.get("explanation", ""),
                    "confidence":   float(meta.get("confidence", 0.0)),
                    "fix_valid":    meta.get("fix_valid", "False") == "True",
                    "op":           meta.get("op", "?"),
                    "ts":           meta.get("ts", ""),
                }
                new_fixes.append(payload)
            except Exception as exc:
                log.warning(f"  ⚠️  Could not parse fix {fix_id}: {exc}")

        return new_fixes

    except Exception as exc:
        log.error(f"❌ ChromaDB fetch error: {exc}")
        return []


# ── Validation pipeline ───────────────────────────────────────────────────────
def run_validations(fix_payload: dict, schema_validator, pydantic_validator, db_validator) -> list[str]:
    """
    Run all 3 validation layers.
    Returns combined list of errors (empty = all passed).
    """
    all_errors = []

    fixed_record = fix_payload.get("fixed", {})
    op           = fix_payload.get("op", "?")
    fix_id       = fix_payload.get("fix_id", "?")

    # ── Layer 1: JSON Schema ──────────────────────────────────────────
    log.info(f"  📋 Layer 1 — JSON Schema validation...")
    schema_errors = schema_validator.validate_fix_payload(fix_payload)
    if schema_errors:
        log.warning(f"  ⚠️  Schema errors: {schema_errors}")
        all_errors.extend(schema_errors)
    else:
        log.info(f"  ✅ Layer 1 passed.")

    # ── Layer 2: Pydantic ─────────────────────────────────────────────
    log.info(f"  🔍 Layer 2 — Pydantic type/value validation...")
    try:
        from validators.pydantic_models import CustomerRecord
        CustomerRecord(**fixed_record)
        log.info(f"  ✅ Layer 2 passed.")
    except Exception as exc:
        err = f"[PYDANTIC] {str(exc)}"
        log.warning(f"  ⚠️  {err}")
        all_errors.append(err)

    # ── Layer 3: DB dry-run ───────────────────────────────────────────
    log.info(f"  🗄️  Layer 3 — DB constraint dry-run...")
    db_errors = db_validator.validate(fixed_record, op)
    if db_errors:
        log.warning(f"  ⚠️  DB errors: {db_errors}")
        all_errors.extend(db_errors)
    else:
        log.info(f"  ✅ Layer 3 passed.")

    return all_errors


# ── FastAPI in background thread ──────────────────────────────────────────────
def _start_api(queue, notifier, applier):
    from approval.api import app, init_api
    init_api(queue, notifier, applier)

    config = uvicorn.Config(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level="warning",   # suppress uvicorn info spam
    )
    server = uvicorn.Server(config)
    log.info(f"🌐 Approval API starting on http://{API_HOST}:{API_PORT}")
    server.run()


# ── Main loop ─────────────────────────────────────────────────────────────────
def run():
    log.info("🔎 Checker Agent starting...")

    # Initialise all components
    from validators.schema_validator import SchemaValidator
    from validators.db_validator     import DBValidator
    from approval.queue              import ApprovalQueue
    from approval.notifier           import Notifier
    from applier                     import Applier

    schema_validator = SchemaValidator()
    db_validator     = DBValidator()
    queue            = ApprovalQueue()
    notifier         = Notifier()
    applier          = Applier()

    # Start FastAPI server in background
    api_thread = threading.Thread(
        target=_start_api,
        args=(queue, notifier, applier),
        daemon=True,
    )
    api_thread.start()

    log.info(
        f"✅ Checker ready — polling ChromaDB every {POLL_INTERVAL_SECONDS}s "
        f"| auto-approve threshold: {AUTO_APPROVE_THRESHOLD:.0%}"
    )

    while True:
        new_fixes = fetch_new_fixes()

        if new_fixes:
            log.info(f"📦 Found {len(new_fixes)} new fix(es) to process.")

        for fix_payload in new_fixes:
            fix_id     = fix_payload["fix_id"]
            confidence = fix_payload["confidence"]
            op         = fix_payload["op"]
            fix_valid  = fix_payload["fix_valid"]

            log.info(
                f"\n{'─'*60}\n"
                f"🔎 Processing fix_id={fix_id}\n"
                f"   op={op} confidence={confidence:.0%} "
                f"fix_valid(W3)={fix_valid}"
            )

            # ── Run all validations ───────────────────────────────────
            errors = run_validations(
                fix_payload, schema_validator, db_validator, db_validator
            )

            # ── Routing decision ──────────────────────────────────────
            all_passed  = len(errors) == 0
            high_conf   = confidence >= AUTO_APPROVE_THRESHOLD

            if all_passed and high_conf:
                # ── AUTO-APPROVE PATH ─────────────────────────────────
                log.info(
                    f"  🚀 AUTO-APPROVE — confidence={confidence:.0%} "
                    f"≥ threshold={AUTO_APPROVE_THRESHOLD:.0%}, all checks passed."
                )
                applied = applier.apply(fix_payload)
                if applied:
                    log.info(f"  ✅ Fix written to MySQL — fix_id={fix_id}")
                    notifier.notify_applied(fix_id, fix_payload.get("original", {}).get("id", "?"))
                else:
                    log.error(f"  ❌ Auto-apply FAILED — fix_id={fix_id}")

            else:
                # ── HUMAN REVIEW PATH ─────────────────────────────────
                reason_parts = []
                if not high_conf:
                    reason_parts.append(f"confidence {confidence:.0%} < threshold {AUTO_APPROVE_THRESHOLD:.0%}")
                if not all_passed:
                    reason_parts.append(f"{len(errors)} validation error(s)")

                log.warning(
                    f"  👤 HUMAN REVIEW required — {' | '.join(reason_parts)}"
                )

                # Attach validation errors to payload for the UI
                fix_payload["validation_errors"] = errors
                fix_payload["review_reason"]     = " | ".join(reason_parts)

                queued = queue.push_pending(fix_payload)
                if queued:
                    notifier.notify_pending(fix_payload)
                    log.info(f"  📬 Notification sent — pending human decision.")
                else:
                    log.error(f"  ❌ Failed to queue fix_id={fix_id} for human review.")

            # Mark as processed regardless of outcome
            _processed_ids.add(fix_id)

        # Wait before next poll
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
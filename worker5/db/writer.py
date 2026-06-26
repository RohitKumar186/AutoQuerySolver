"""
db/writer.py
Worker 5 — Core database writer.

Flow for every approved fix:
  BEGIN transaction
    → SAVEPOINT before_fix
    → UPDATE customers SET fixed_fields WHERE id=record_id
    → SELECT fixed_fields WHERE id=record_id   ← read-back verification
    → if matches  → RELEASE SAVEPOINT → COMMIT  ✅
    → if mismatch → ROLLBACK TO SAVEPOINT       ❌
"""

import logging
from datetime import datetime, timezone
from sqlalchemy import text
from db.connection import get_engine

log = logging.getLogger("DBWriter")


def apply_fix(fix_payload: dict) -> dict:
    """
    Applies a single approved fix to the live MySQL database.

    fix_payload shape (from Worker 4 Redis queue):
    {
        "record_id":    5,
        "table":        "customers",
        "fixed_record": { "name": "Rohit Singh", "phone": "UNKNOWN" },
        "original":     { "id": 5, "name": "Rohit Sin11", "phone": "not-a-phone" },
        "confidence":   0.91,
        "approved_by":  "AUTO",
        "explanation":  "Fixed typo in name. Phone is garbage, set to UNKNOWN.",
        "ts":           "14:30:00"
    }

    Returns result dict:
    {
        "status":      "SUCCESS" | "ROLLED_BACK" | "ERROR",
        "record_id":   5,
        "applied":     { ...fixed fields... },
        "verified":    True | False,
        "reason":      "explanation string",
        "ts":          "14:30:05"
    }
    """
    record_id    = fix_payload.get("record_id")
    table        = fix_payload.get("table", "customers")
    fixed_record = fix_payload.get("fixed_record", {})
    explanation  = fix_payload.get("explanation", "")
    ts           = datetime.now(timezone.utc).strftime("%H:%M:%S")

    if not record_id or not fixed_record:
        log.error("  ❌ Writer: missing record_id or fixed_record — skipping.")
        return {
            "status":    "ERROR",
            "record_id": record_id,
            "applied":   {},
            "verified":  False,
            "reason":    "Missing record_id or fixed_record in payload",
            "ts":        ts,
        }

    # ── Build SET clause dynamically from fixed_record fields ──────────────────
    # e.g. fixed_record = {"name": "Rohit Singh", "phone": "UNKNOWN"}
    # → SET name = :name, phone = :phone
    set_clause = ", ".join([f"{col} = :{col}" for col in fixed_record.keys()])
    params     = {**fixed_record, "record_id": record_id}

    update_sql = text(f"UPDATE {table} SET {set_clause} WHERE id = :record_id")
    select_sql = text(
        f"SELECT {', '.join(fixed_record.keys())} FROM {table} WHERE id = :record_id"
    )

    engine = get_engine()

    try:
        with engine.begin() as conn:
            # ── SAVEPOINT — the Minecraft checkpoint ──────────────────
            conn.execute(text("SAVEPOINT before_fix"))
            log.info(f"  💾 SAVEPOINT created for record id={record_id}")

            # ── UPDATE ────────────────────────────────────────────────
            result = conn.execute(update_sql, params)
            rows_affected = result.rowcount
            log.info(f"  ✏️  UPDATE executed — {rows_affected} row(s) affected")

            if rows_affected == 0:
                log.warning(f"  ⚠️  No rows updated — record id={record_id} may not exist.")
                conn.execute(text("ROLLBACK TO SAVEPOINT before_fix"))
                return {
                    "status":    "ROLLED_BACK",
                    "record_id": record_id,
                    "applied":   {},
                    "verified":  False,
                    "reason":    f"No rows found with id={record_id}",
                    "ts":        ts,
                }

            # ── READ-BACK VERIFICATION ────────────────────────────────
            row = conn.execute(select_sql, {"record_id": record_id}).fetchone()

            if row is None:
                log.error(f"  ❌ Read-back failed — record id={record_id} not found after update.")
                conn.execute(text("ROLLBACK TO SAVEPOINT before_fix"))
                return {
                    "status":    "ROLLED_BACK",
                    "record_id": record_id,
                    "applied":   {},
                    "verified":  False,
                    "reason":    "Record not found after UPDATE — rolled back",
                    "ts":        ts,
                }

            # Compare each fixed field with what was actually written
            row_dict  = dict(zip(fixed_record.keys(), row))
            mismatches = []

            for col, expected in fixed_record.items():
                actual = str(row_dict.get(col, ""))
                if str(expected) != actual:
                    mismatches.append(
                        f"{col}: expected '{expected}' but got '{actual}'"
                    )

            if mismatches:
                log.error(
                    f"  ❌ Read-back MISMATCH — rolling back. Issues: {mismatches}"
                )
                conn.execute(text("ROLLBACK TO SAVEPOINT before_fix"))
                return {
                    "status":    "ROLLED_BACK",
                    "record_id": record_id,
                    "applied":   {},
                    "verified":  False,
                    "reason":    f"Read-back mismatch: {mismatches}",
                    "ts":        ts,
                }

            # ── ALL GOOD — release savepoint and commit ───────────────
            conn.execute(text("RELEASE SAVEPOINT before_fix"))
            log.info(
                f"  ✅ Fix COMMITTED — id={record_id} "
                f"fields={list(fixed_record.keys())} "
                f"values={list(fixed_record.values())}"
            )

            return {
                "status":    "SUCCESS",
                "record_id": record_id,
                "applied":   fixed_record,
                "verified":  True,
                "reason":    explanation,
                "ts":        ts,
            }

    except Exception as exc:
        log.error(f"  ❌ Writer exception for id={record_id}: {exc}", exc_info=True)
        return {
            "status":    "ERROR",
            "record_id": record_id,
            "applied":   {},
            "verified":  False,
            "reason":    str(exc),
            "ts":        ts,
        }
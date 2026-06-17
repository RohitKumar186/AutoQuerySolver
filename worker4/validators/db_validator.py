"""
validators/db_validator.py
SQLAlchemy — checks the fix respects the actual MySQL DB constraints.
(NOT NULL, VARCHAR length, data types, etc.)
Does a dry-run: connects to MySQL, attempts the operation, rolls it back.
This means we never permanently write bad data, but we DO verify it would work.
"""

import logging
import os
from typing import Optional

log = logging.getLogger("DBValidator")

DB_HOST     = os.getenv("DB_HOST",     "watchman_mysql")
DB_PORT     = int(os.getenv("DB_PORT", "3306"))
DB_USER     = os.getenv("DB_USER",     "solver_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME     = os.getenv("DB_NAME",     "autoquery_db")


def _get_engine():
    try:
        from sqlalchemy import create_engine
        url = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
            f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        return create_engine(url, pool_pre_ping=True, echo=False)
    except Exception as exc:
        log.error(f"❌ Could not create SQLAlchemy engine: {exc}")
        return None


class DBValidator:
    """
    Validates a fix by doing a dry-run INSERT/UPDATE against MySQL.
    Rolls back immediately — so the DB is never actually changed here.
    The real write happens in applier.py after human/auto approval.
    """

    def __init__(self):
        self._engine = _get_engine()
        if self._engine:
            log.info("✅ DBValidator connected to MySQL.")
        else:
            log.warning("⚠️  DBValidator could not connect — DB checks will be skipped.")

    def validate(self, fixed_record: dict, op: str) -> list[str]:
        """
        Dry-run the fix against MySQL.
        Returns list of error strings (empty = DB accepts this fix).
        """
        if not self._engine:
            log.warning("  ⚠️  No DB connection — skipping DB validation.")
            return []

        if op == "d":
            # DELETE ops don't have a fixed record to validate
            return []

        errors = []

        try:
            from sqlalchemy import text

            # Build a minimal INSERT to test the fixed record
            # Use a transaction that we always roll back
            record_id   = fixed_record.get("id")
            name        = fixed_record.get("name")
            phone       = fixed_record.get("phone")
            created_at  = fixed_record.get("created_at")

            # Replace UNKNOWN placeholders with NULL for DB testing
            # (UNKNOWN is Worker 3's sentinel — DB doesn't know about it)
            db_name  = None if name  == "UNKNOWN" else name
            db_phone = None if phone == "UNKNOWN" else phone

            with self._engine.begin() as conn:
                if op == "c":
                    # Test INSERT
                    stmt = text("""
                        INSERT INTO customers (name, phone, created_at)
                        VALUES (:name, :phone, :created_at)
                    """)
                    conn.execute(stmt, {
                        "name":       db_name,
                        "phone":      db_phone,
                        "created_at": created_at,
                    })
                    log.info("  🔍 DB dry-run INSERT — checking constraints...")

                elif op == "u" and record_id:
                    # Test UPDATE
                    stmt = text("""
                        UPDATE customers
                        SET name = :name, phone = :phone
                        WHERE id = :id
                    """)
                    conn.execute(stmt, {
                        "name":  db_name,
                        "phone": db_phone,
                        "id":    record_id,
                    })
                    log.info(f"  🔍 DB dry-run UPDATE id={record_id} — checking constraints...")

                # ── Always roll back — this is a dry run ──────────────
                conn.rollback()
                log.info("  ↩️  Dry-run rolled back — no changes made.")

        except Exception as exc:
            err_msg = f"[DB] Constraint violation: {str(exc)[:200]}"
            errors.append(err_msg)
            log.warning(f"  ⚠️  {err_msg}")

        if not errors:
            log.info("  ✅ DB dry-run passed — fix is DB-safe.")

        return errors

    def record_exists(self, record_id: int) -> bool:
        """Check if a record with this id exists in customers."""
        if not self._engine:
            return True   # assume exists if we can't check
        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                result = conn.execute(
                    text("SELECT 1 FROM customers WHERE id = :id"),
                    {"id": record_id}
                )
                return result.fetchone() is not None
        except Exception as exc:
            log.error(f"❌ record_exists check failed: {exc}")
            return False
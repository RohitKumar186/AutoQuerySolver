"""
applier.py
The only place in the entire system that writes fixes back to MySQL.
Called ONLY after a fix is approved (auto or human).

This is intentionally the LAST step — nothing writes to MySQL until
all validators pass AND approval is given.
"""

import logging
import os

log = logging.getLogger("Applier")

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
        engine = create_engine(url, pool_pre_ping=True, echo=False)
        log.info("✅ Applier connected to MySQL.")
        return engine
    except Exception as exc:
        log.error(f"❌ Applier could not connect to MySQL: {exc}")
        return None


class Applier:
    """
    Writes an approved fix back to MySQL.
    Handles INSERT (op=c) and UPDATE (op=u).
    DELETE fixes are skipped — we never auto-delete based on a fix.
    """

    def __init__(self):
        self._engine = _get_engine()

    def apply(self, fix_payload: dict) -> bool:
        """
        Apply an approved fix to MySQL.
        Returns True on success, False on failure.
        """
        if not self._engine:
            log.error("❌ No DB connection — cannot apply fix.")
            return False

        op           = fix_payload.get("op", "?")
        original     = fix_payload.get("original", {})
        fixed_fields = fix_payload.get("fixed_fields", {})
        fix_id       = fix_payload.get("fix_id", "?")

        if not fixed_fields:
            log.warning(f"  ⚠️  No fixed_fields in payload — nothing to apply. fix_id={fix_id}")
            return False

        if op == "d":
            log.info(f"  ⏭️  Skipping apply for DELETE op — fix_id={fix_id}")
            return True

        record_id = original.get("id")

        try:
            from sqlalchemy import text

            # Replace UNKNOWN with NULL before writing to DB
            db_fields = {
                k: (None if v == "UNKNOWN" else v)
                for k, v in fixed_fields.items()
            }

            with self._engine.begin() as conn:
                if op == "c":
                    # For INSERT events: update the row that was just inserted
                    # (it already exists in DB from the original CDC event)
                    if record_id:
                        set_clause = ", ".join(
                            f"{col} = :{col}" for col in db_fields
                        )
                        stmt = text(f"""
                            UPDATE customers
                            SET {set_clause}
                            WHERE id = :__id
                        """)
                        conn.execute(stmt, {**db_fields, "__id": record_id})
                        log.info(
                            f"  ✏️  Applied fix via UPDATE (original was INSERT) "
                            f"— id={record_id} fields={list(db_fields.keys())} fix_id={fix_id}"
                        )
                    else:
                        log.warning(f"  ⚠️  INSERT fix has no id — cannot locate row. fix_id={fix_id}")
                        return False

                elif op == "u":
                    if not record_id:
                        log.warning(f"  ⚠️  UPDATE fix has no id. fix_id={fix_id}")
                        return False
                    set_clause = ", ".join(
                        f"{col} = :{col}" for col in db_fields
                    )
                    stmt = text(f"""
                        UPDATE customers
                        SET {set_clause}
                        WHERE id = :__id
                    """)
                    conn.execute(stmt, {**db_fields, "__id": record_id})
                    log.info(
                        f"  ✏️  Applied fix via UPDATE "
                        f"— id={record_id} fields={list(db_fields.keys())} fix_id={fix_id}"
                    )

            log.info(f"  ✅ Fix successfully written to MySQL — fix_id={fix_id}")
            return True

        except Exception as exc:
            log.error(f"  ❌ Apply failed — fix_id={fix_id}: {exc}", exc_info=True)
            return False
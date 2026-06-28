"""
worker6/services/audit_writer.py
Writes one row to audit_log per fix event.
Append-only — no updates, no deletes.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker, Session

from models.audit_log import AuditLog

log = logging.getLogger("AuditWriter")


class AuditWriter:
    def __init__(self, engine):
        self._Session = sessionmaker(bind=engine, expire_on_commit=False)

    def write(self, event: dict) -> AuditLog | None:
        """
        Persist a fix event to audit_log.
        Returns the saved AuditLog row, or None on error.

        Expected event shape (from Worker 5 or pipeline ingest):
        {
            "op":          "c" | "u" | "d",
            "record_id":   int,
            "original":    dict,
            "fixed":       dict,
            "issues":      list,
            "confidence":  float,
            "fix_valid":   bool,
            "approved_by": "auto" | email_str,
            "explanation": str,
            "worker":      "worker5",
            "ts":          "HH:MM:SS",
        }
        """
        session: Session = self._Session()
        try:
            row = AuditLog(
                worker      = event.get("worker", "worker5"),
                op          = event.get("op", "?"),
                record_id   = event.get("record_id"),
                original    = json.dumps(event.get("original") or {}),
                fixed       = json.dumps(event.get("fixed") or {}),
                issues      = json.dumps(event.get("issues") or []),
                confidence  = event.get("confidence"),
                fix_valid   = event.get("fix_valid"),
                approved_by = event.get("approved_by"),
                explanation = event.get("explanation"),
                ts          = datetime.now(timezone.utc),
            )
            session.add(row)
            session.commit()
            log.info(
                f"  💾 Audit row saved — id={row.id} "
                f"op={row.op} record_id={row.record_id} "
                f"confidence={row.confidence}"
            )
            return row

        except Exception as exc:
            session.rollback()
            log.error(f"  ❌ AuditWriter error: {exc}", exc_info=True)
            return None

        finally:
            session.close()

    def fetch_recent(self, limit: int = 100) -> list[dict]:
        """Return the most recent audit rows as dicts (for API / dashboard)."""
        session: Session = self._Session()
        try:
            rows = (
                session.query(AuditLog)
                .order_by(AuditLog.ts.desc())
                .limit(limit)
                .all()
            )
            return [r.to_dict() for r in rows]
        except Exception as exc:
            log.error(f"  ❌ fetch_recent error: {exc}")
            return []
        finally:
            session.close()

    def fetch_stats(self) -> dict:
        """
        Return aggregate stats for the report endpoint.
        Keeps it simple — pure Python aggregation over recent rows.
        """
        session: Session = self._Session()
        try:
            rows = session.query(AuditLog).all()
            total        = len(rows)
            valid_fixes  = sum(1 for r in rows if r.fix_valid)
            auto_approved= sum(1 for r in rows if r.approved_by == "auto")
            human_approved=sum(1 for r in rows if r.approved_by and r.approved_by != "auto")
            confidences  = [r.confidence for r in rows if r.confidence is not None]
            avg_conf     = round(sum(confidences) / len(confidences), 3) if confidences else 0.0

            ops = {}
            for r in rows:
                ops[r.op] = ops.get(r.op, 0) + 1

            return {
                "total_events":     total,
                "valid_fixes":      valid_fixes,
                "invalid_fixes":    total - valid_fixes,
                "auto_approved":    auto_approved,
                "human_approved":   human_approved,
                "avg_confidence":   avg_conf,
                "ops_breakdown":    ops,
            }
        except Exception as exc:
            log.error(f"  ❌ fetch_stats error: {exc}")
            return {}
        finally:
            session.close()
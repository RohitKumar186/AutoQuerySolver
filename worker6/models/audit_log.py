"""
worker6/models/audit_log.py
SQLAlchemy model for the append-only audit_log table.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, event
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AuditLog(Base):
    __tablename__ = "audit_log"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    worker      = Column(String(20),  nullable=False, default="worker6")
    op          = Column(String(10),  nullable=False)
    record_id   = Column(Integer,     nullable=True)
    original    = Column(Text,        nullable=True)
    fixed       = Column(Text,        nullable=True)
    issues      = Column(Text,        nullable=True)
    confidence  = Column(Float,       nullable=True)
    fix_valid   = Column(Boolean,     nullable=True)
    approved_by = Column(String(100), nullable=True)
    explanation = Column(Text,        nullable=True)
    ts          = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "worker":      self.worker,
            "op":          self.op,
            "record_id":   self.record_id,
            "original":    _safe_json(self.original),
            "fixed":       _safe_json(self.fixed),
            "issues":      _safe_json(self.issues),
            "confidence":  self.confidence,
            "fix_valid":   self.fix_valid,
            "approved_by": self.approved_by,
            "explanation": self.explanation,
            "ts":          self.ts.isoformat() if self.ts else None,
        }


def _safe_json(value):
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


@event.listens_for(AuditLog, "before_update")
def _block_update(mapper, connection, target):
    raise RuntimeError("audit_log is append-only — UPDATE is not allowed.")


@event.listens_for(AuditLog, "before_delete")
def _block_delete(mapper, connection, target):
    raise RuntimeError("audit_log is append-only — DELETE is not allowed.")
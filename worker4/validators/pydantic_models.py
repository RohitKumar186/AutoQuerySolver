"""
validators/pydantic_models.py
Pydantic v2 models that mirror the customers table schema.
Used by Worker 4 to double-check every fix before it touches the DB.

customers table:
    id         INT AUTO_INCREMENT PRIMARY KEY
    name       VARCHAR(255) NOT NULL
    phone      VARCHAR(50)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
"""

import re
import logging
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator

log = logging.getLogger("PydanticModels")

# ── Regex patterns (same as Worker 2 rule_based.py — stay in sync) ────────────
_PHONE_RE = re.compile(r"^\+?[\d\s\-\(\)]{7,15}$")
_NAME_RE  = re.compile(r"^[A-Za-z\s\.\-']{2,100}$")

# Confidence threshold below which we route to human approval queue
AUTO_APPROVE_THRESHOLD = 0.80


class CustomerRecord(BaseModel):
    """
    Validates one row of the customers table.
    Accepts UNKNOWN as a valid placeholder for unfixable fields
    (matches Worker 3's fixer.py convention).
    """
    id:         Optional[int]   = None
    name:       str
    phone:      Optional[str]   = None
    created_at: Optional[str]   = None

    # ── Field validators ──────────────────────────────────────────────────────

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if v in ("UNKNOWN", "NEEDS_CORRECTION"):
            return v                         # UNKNOWN is an accepted placeholder
        if not v or not v.strip():
            raise ValueError("name cannot be empty")
        if len(v) > 255:
            raise ValueError(f"name too long ({len(v)} chars, max 255)")
        if not _NAME_RE.match(v):
            raise ValueError(
                f"name '{v}' contains invalid characters "
                "(only letters, spaces, hyphens, apostrophes, dots allowed)"
            )
        return v.strip()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v in ("UNKNOWN", "NEEDS_CORRECTION"):
            return v                         # NULL and UNKNOWN both accepted
        v = v.strip()
        if not _PHONE_RE.match(v):
            raise ValueError(
                f"phone '{v}' does not match international format "
                "(e.g. +91-9876543210)"
            )
        return v

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError(f"id must be a positive integer, got {v}")
        return v

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Accept ISO timestamps and MySQL TIMESTAMP strings
        _DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T][\d:]+Z?)?$")
        if not _DATE_RE.match(str(v)):
            raise ValueError(
                f"created_at '{v}' is not a valid date/timestamp"
            )
        return v

    @model_validator(mode="after")
    def check_name_not_all_unknown(self) -> "CustomerRecord":
        """Warn if every fixable field ended up as UNKNOWN — fix is useless."""
        if self.name == "UNKNOWN" and self.phone == "UNKNOWN":
            log.warning(
                "⚠️  Both name and phone are UNKNOWN — "
                "fix may not be useful but is technically valid."
            )
        return self


class FixPayload(BaseModel):
    """
    Validates the full fix payload that Worker 3's saver.py writes to ChromaDB.
    This is what checker_agent.py reads and passes through the pipeline.
    """
    fix_id:       str
    original:     dict
    issues:       list
    fixed:        dict
    fixed_fields: dict
    explanation:  str
    confidence:   float
    fix_valid:    bool
    op:           str
    ts:           str

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v

    @field_validator("op")
    @classmethod
    def validate_op(cls, v: str) -> str:
        allowed = {"c", "u", "d", "r"}
        if v not in allowed:
            raise ValueError(f"op must be one of {allowed}, got '{v}'")
        return v

    @property
    def needs_human_approval(self) -> bool:
        """True when confidence is too low for auto-approval."""
        return self.confidence < AUTO_APPROVE_THRESHOLD

    @property
    def customer_record(self) -> CustomerRecord:
        """Parse the fixed dict into a validated CustomerRecord."""
        return CustomerRecord(**self.fixed)
"""
Rule-Based Checker
Uses Python regex + Pandera to validate formats and data types.
"""

import re
import logging
import pandas as pd

try:
    import pandera as pa
    from pandera import Column, DataFrameSchema, Check
    PANDERA_AVAILABLE = True
except ImportError:
    PANDERA_AVAILABLE = False

log = logging.getLogger("RuleBasedChecker")

# ── Regex patterns ─────────────────────────────────────────────────────────────
PATTERNS = {
    "email":  re.compile(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$"),
    "phone":  re.compile(r"^\+?[\d\s\-\(\)]{7,15}$"),
    "date":   re.compile(r"^\d{4}-\d{2}-\d{2}$"),          # YYYY-MM-DD
    "name":   re.compile(r"^[A-Za-z\s\.\-']{2,100}$"),
}

# ── Field → expected type / pattern mapping ────────────────────────────────────
# Extend this to match YOUR table's columns.
FIELD_RULES = {
    "email":      ("pattern", "email"),
    "phone":      ("pattern", "phone"),
    "created_at": ("pattern", "date"),
    "dob":        ("pattern", "date"),
    "name":       ("pattern", "name"),
    "first_name": ("pattern", "name"),
    "last_name":  ("pattern", "name"),
    "age":        ("type",    int),
    "score":      ("type",    (int, float)),
}

# ── Optional Pandera schema ────────────────────────────────────────────────────
if PANDERA_AVAILABLE:
    PANDERA_SCHEMA = DataFrameSchema(
        {
            "email": Column(str, nullable=True, checks=Check.str_matches(PATTERNS["email"])),
            "age":   Column(float, nullable=True, checks=Check.in_range(0, 150)),
        },
        coerce=True,
    )


class RuleBasedChecker:
    def check(self, record: dict) -> list[str]:
        issues = []

        for field, value in record.items():
            if value is None:
                continue

            rule = FIELD_RULES.get(field)
            if not rule:
                continue

            kind, spec = rule

            if kind == "pattern":
                pattern = PATTERNS.get(spec)
                if pattern and not pattern.match(str(value)):
                    issues.append(
                        f"[FORMAT] '{field}' value '{value}' does not match {spec} pattern"
                    )

            elif kind == "type":
                if not isinstance(value, spec):
                    issues.append(
                        f"[TYPE] '{field}' expected {spec}, got {type(value).__name__} (value={value!r})"
                    )

        # ── Pandera deep validation ────────────────────────────────────
        if PANDERA_AVAILABLE:
            try:
                df = pd.DataFrame([record])
                PANDERA_SCHEMA.validate(df, lazy=True)
            except pa.errors.SchemaErrors as exc:
                for _, row in exc.failure_cases.iterrows():
                    issues.append(
                        f"[PANDERA] column='{row['column']}' check='{row['check']}' "
                        f"failure_case='{row['failure_case']}'"
                    )
            except Exception:
                pass   # Column not present in this record — skip silently

        return issues
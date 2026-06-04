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
    "date":   re.compile(r"^\d{4}-\d{2}-\d{2}(T[\d:]+Z?)?$"),   # YYYY-MM-DD or ISO
    "name":   re.compile(r"^[A-Za-z\s\.\-']{2,100}$"),
}

# ── Field → expected type / pattern mapping ────────────────────────────────────
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

# ── Pandera schema — matches actual customers table columns ────────────────────
if PANDERA_AVAILABLE:
    PANDERA_SCHEMA = DataFrameSchema(
        {
            "id":         Column(object, nullable=True),   # int or None on insert
            "name":       Column(str, nullable=False, checks=Check.str_length(2, 255)),
            "phone":      Column(str, nullable=True),
            "created_at": Column(object, nullable=True),   # timestamp string
        },
        strict=False,   # ignore any extra columns
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
                pass

        return issues
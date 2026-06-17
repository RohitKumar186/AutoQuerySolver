"""
validators/schema_validator.py
JSON Schema validation — defines what a valid fix payload looks like in code.
First gate before Pydantic and DB checks.
"""

import logging
from typing import Optional

log = logging.getLogger("SchemaValidator")

# ── JSON Schema definition ────────────────────────────────────────────────────
# Mirrors the shape Worker 3's saver.py writes to ChromaDB metadata.
# jsonschema lib validates structure; Pydantic validates values.

CUSTOMERS_RECORD_SCHEMA = {
    "type": "object",
    "properties": {
        "id":         {"type": ["integer", "null"], "minimum": 1},
        "name":       {"type": "string",  "minLength": 2, "maxLength": 255},
        "phone":      {"type": ["string", "null"]},
        "created_at": {"type": ["string", "null"]},
    },
    "required": ["name"],
    "additionalProperties": True,   # allow extra fields from CDC envelope
}

FIX_PAYLOAD_SCHEMA = {
    "type": "object",
    "properties": {
        "fix_id":       {"type": "string",  "minLength": 1},
        "original":     {"type": "object"},
        "issues":       {"type": "array",   "items": {"type": "string"}},
        "fixed":        {"type": "object"},
        "fixed_fields": {"type": "object"},
        "explanation":  {"type": "string"},
        "confidence":   {"type": "number",  "minimum": 0.0, "maximum": 1.0},
        "fix_valid":    {"type": "boolean"},
        "op":           {"type": "string",  "enum": ["c", "u", "d", "r"]},
        "ts":           {"type": "string"},
    },
    "required": [
        "fix_id", "original", "issues",
        "fixed", "fixed_fields", "explanation",
        "confidence", "fix_valid", "op", "ts",
    ],
    "additionalProperties": False,
}


class SchemaValidator:
    """
    Validates fix payloads and customer records against JSON Schemas.
    Returns list of error strings (empty = valid).
    """

    def __init__(self):
        try:
            import jsonschema
            self._jsonschema = jsonschema
            self._available  = True
            log.info("✅ jsonschema available — SchemaValidator ready.")
        except ImportError:
            log.warning("⚠️  jsonschema not installed — schema validation skipped.")
            self._available = False

    def validate_fix_payload(self, payload: dict) -> list[str]:
        """Validate the full fix payload shape."""
        return self._validate(payload, FIX_PAYLOAD_SCHEMA, label="FIX_PAYLOAD")

    def validate_customer_record(self, record: dict) -> list[str]:
        """Validate a single customer record shape."""
        return self._validate(record, CUSTOMERS_RECORD_SCHEMA, label="CUSTOMER_RECORD")

    def _validate(self, data: dict, schema: dict, label: str) -> list[str]:
        if not self._available:
            return []

        errors = []
        validator = self._jsonschema.Draft7Validator(schema)

        for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
            path  = " → ".join(str(p) for p in error.path) or "root"
            msg   = f"[SCHEMA:{label}] {path}: {error.message}"
            errors.append(msg)
            log.warning(f"  {msg}")

        if not errors:
            log.info(f"  ✅ Schema valid — {label}")

        return errors
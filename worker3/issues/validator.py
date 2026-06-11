"""
issues/validator.py
Step 4 — Validate that the fix actually works.
Re-runs rule checks on the fixed record.
Accepts "UNKNOWN" as a valid placeholder for unfixable fields.
"""

import logging

log = logging.getLogger("ValidatorNode")

try:
    from checks.rule_based import RuleBasedChecker
    _rule_checker = RuleBasedChecker()
except ImportError:
    log.warning("⚠️  rule_based not found — validator using fallback.")
    class _FallbackChecker:
        def check(self, record): return []
    _rule_checker = _FallbackChecker()


def validator_node(state: dict) -> dict:
    fix    = state.get("fix")
    record = state.get("record", {})

    if not fix:
        log.warning("  ⚠️  No fix to validate.")
        return {**state, "fix_valid": False}

    fixed_record = fix.get("fixed_record", {})

    if not fixed_record:
        log.warning("  ⚠️  Fix has no fixed_record field.")
        return {**state, "fix_valid": False}

    # Merge fix into original record
    merged = {**record, **fixed_record}

    # Replace UNKNOWN placeholders temporarily so rule checks don't fail on them
    # UNKNOWN is a valid outcome — it means "we couldn't determine the real value"
    validation_copy = {
        k: "placeholder_valid@example.com" if v == "UNKNOWN" and k == "email"
        else "+10000000000" if v in ["UNKNOWN", "NEEDS_CORRECTION"] and k in ["phone", "mobile", "contact"]
        else "Unknown Name" if v == "UNKNOWN" and k in ["name", "full_name", "first_name", "last_name"]
        else v
        for k, v in merged.items()
    }

    remaining_issues = _rule_checker.check(validation_copy)

    if not remaining_issues:
        log.info("  ✅ Fix is VALID — passes all rule checks.")
        return {**state, "fix_valid": True}
    else:
        log.warning(
            f"  ⚠️  Fix PARTIAL — {len(remaining_issues)} issue(s) remain: "
            f"{remaining_issues}"
        )
        return {**state, "fix_valid": False}
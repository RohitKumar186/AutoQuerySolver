"""
nodes/check_issues.py
Step 0 — Re-runs Worker 2's rule-based + duplicate checks on the record.
If no issues → skipped=True → pipeline ends.
If issues found → pipeline continues to embed → search → fixer → validator → saver.
"""

import logging

log = logging.getLogger("CheckIssuesNode")

try:
    from checks.rule_based import RuleBasedChecker
    from checks.duplicate  import DuplicateChecker
    _rule_checker = RuleBasedChecker()
    _dup_checker  = DuplicateChecker()
    log.info("✅ Worker 2 checkers loaded successfully.")
except ImportError:
    log.warning("⚠️  Worker 2 checks not found — using fallback.")
    class _FallbackChecker:
        def check(self, record): return []
    _rule_checker = _FallbackChecker()
    _dup_checker  = _FallbackChecker()


def check_issues_node(state: dict) -> dict:
    record = state.get("record", {})

    if not record:
        log.warning("Empty record — skipping.")
        return {**state, "issues": [], "skipped": True}

    issues = []

    rule_issues = _rule_checker.check(record)
    if rule_issues:
        issues.extend(rule_issues)
        log.warning(f"  ⚠️  Rule issues: {rule_issues}")

    dup_issues = _dup_checker.check(record)
    if dup_issues:
        issues.extend(dup_issues)
        log.warning(f"  🔁 Duplicate issues: {dup_issues}")

    if not issues:
        log.info("  ✅ Record is clean — Doctor skipping.")
        return {**state, "issues": [], "skipped": True}

    log.info(f"  🚨 {len(issues)} issue(s) found — Doctor will fix.")
    return {**state, "issues": issues, "skipped": False}
"""
worker6/services/report_builder.py
Builds human-readable summary reports from audit_log stats.
Called by reporter_node and the /report API endpoint.
"""

import logging
from datetime import datetime, timezone

log = logging.getLogger("ReportBuilder")


class ReportBuilder:
    def build(self, stats: dict, recent_rows: list[dict]) -> dict:
        """
        Takes raw stats dict (from AuditWriter.fetch_stats) and recent rows,
        returns a structured report dict ready for JSON serialization.
        """
        if not stats:
            return {"error": "No stats available yet."}

        total        = stats.get("total_events", 0)
        valid        = stats.get("valid_fixes", 0)
        invalid      = stats.get("invalid_fixes", 0)
        auto_app     = stats.get("auto_approved", 0)
        human_app    = stats.get("human_approved", 0)
        avg_conf     = stats.get("avg_confidence", 0.0)
        ops          = stats.get("ops_breakdown", {})

        fix_rate = round(valid / total * 100, 1) if total > 0 else 0.0

        # ── Issue type breakdown from recent rows ──────────────────────
        issue_counts = {}
        for row in recent_rows:
            issues = row.get("issues") or []
            if isinstance(issues, list):
                for issue in issues:
                    tag = issue.split("]")[0].lstrip("[") if "]" in issue else "OTHER"
                    issue_counts[tag] = issue_counts.get(tag, 0) + 1

        # ── Most common field fixed ────────────────────────────────────
        field_counts = {}
        for row in recent_rows:
            fixed = row.get("fixed") or {}
            original = row.get("original") or {}
            if isinstance(fixed, dict) and isinstance(original, dict):
                for k, v in fixed.items():
                    if original.get(k) != v:
                        field_counts[k] = field_counts.get(k, 0) + 1

        top_fields = sorted(field_counts.items(), key=lambda x: -x[1])[:5]

        return {
            "generated_at":    datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_events":    total,
                "valid_fixes":     valid,
                "invalid_fixes":   invalid,
                "fix_success_rate": f"{fix_rate}%",
                "avg_confidence":  avg_conf,
            },
            "approval": {
                "auto_approved":   auto_app,
                "human_approved":  human_app,
            },
            "operations": ops,
            "issue_types": issue_counts,
            "top_fixed_fields": dict(top_fields),
            "narrative": _narrative(fix_rate, avg_conf, total, issue_counts),
        }

    def build_dashboard_payload(self, stats: dict, audit_row: dict) -> dict:
        """
        Lightweight payload for WebSocket broadcast to dashboard.
        Sent after every fix event — dashboard updates in real time.
        """
        return {
            "type":       "audit_event",
            "audit_row":  audit_row,
            "live_stats": {
                "total":       stats.get("total_events", 0),
                "valid":       stats.get("valid_fixes", 0),
                "avg_conf":    stats.get("avg_confidence", 0.0),
                "auto_app":    stats.get("auto_approved", 0),
                "human_app":   stats.get("human_approved", 0),
            },
        }


def _narrative(fix_rate: float, avg_conf: float, total: int, issue_counts: dict) -> str:
    """Generate a short plain-English summary sentence."""
    if total == 0:
        return "No fix events recorded yet."

    top_issue = max(issue_counts, key=issue_counts.get) if issue_counts else "UNKNOWN"

    quality = (
        "excellent" if avg_conf >= 0.9
        else "good" if avg_conf >= 0.75
        else "moderate"
    )

    return (
        f"Out of {total} event(s) processed, {fix_rate}% were successfully fixed "
        f"with {quality} confidence (avg {avg_conf:.2f}). "
        f"The most common issue type was [{top_issue}]."
    )
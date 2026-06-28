"""
worker6/nodes/reporter_node.py
Step 4 — Build the report payload that gets broadcast to the dashboard.
Pulls live stats from MySQL, builds a structured report dict.
"""

import logging

log = logging.getLogger("ReporterNode")


def build_reporter_node(audit_writer, report_builder):
    def reporter_node(state: dict) -> dict:
        if state.get("skipped"):
            return state

        log.info("  📊 Building report payload …")

        try:
            stats       = audit_writer.fetch_stats()
            recent_rows = audit_writer.fetch_recent(limit=50)
            audit_row   = state.get("audit_row")

            dashboard_payload = report_builder.build_dashboard_payload(
                stats, audit_row
            )
            full_report = report_builder.build(stats, recent_rows)

            log.info(
                f"  ✅ Report built — "
                f"total={stats.get('total_events', 0)} "
                f"valid={stats.get('valid_fixes', 0)}"
            )

            return {
                **state,
                "dashboard_payload": dashboard_payload,
                "full_report":       full_report,
            }

        except Exception as exc:
            log.error(f"  ❌ Reporter error: {exc}", exc_info=True)
            return {**state, "dashboard_payload": None, "full_report": None}

    return reporter_node
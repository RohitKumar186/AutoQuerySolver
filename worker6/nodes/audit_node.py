"""
worker6/nodes/audit_node.py
Step 2 — Write the fix event to the append-only audit_log table in MySQL.
Every event (fix or clean) gets one row.
"""

import logging

log = logging.getLogger("AuditNode")


def build_audit_node(audit_writer):
    def audit_node(state: dict) -> dict:
        if state.get("skipped"):
            return state

        log.info("  💾 Writing to audit_log …")

        row = audit_writer.write({
            "worker":      state.get("worker", "worker5"),
            "op":          state.get("op", "?"),
            "record_id":   state.get("record_id"),
            "original":    state.get("original", {}),
            "fixed":       state.get("fixed", {}),
            "issues":      state.get("issues", []),
            "confidence":  state.get("confidence"),
            "fix_valid":   state.get("fix_valid"),
            "approved_by": state.get("approved_by"),
            "explanation": state.get("explanation", ""),
            "ts":          state.get("ts", ""),
        })

        if row:
            log.info(f"  ✅ Audit row created — audit_id={row.id}")
            return {**state, "audit_id": row.id, "audit_row": row.to_dict()}
        else:
            log.warning("  ⚠️  Audit write failed — continuing pipeline.")
            return {**state, "audit_id": None, "audit_row": None}

    return audit_node
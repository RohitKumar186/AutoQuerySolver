"""
worker6/nodes/broadcast_node.py
Step 5 — Push the dashboard payload to all connected WebSocket clients.
"""

import logging

log = logging.getLogger("BroadcastNode")


def build_broadcast_node(broadcast_fn):
    def broadcast_node(state: dict) -> dict:
        if state.get("skipped"):
            return state

        payload = state.get("dashboard_payload")
        if not payload:
            log.warning("  ⚠️  No dashboard payload — broadcast skipped.")
            return state

        try:
            broadcast_fn(payload)
            log.info("  📡 Dashboard broadcast sent.")
        except Exception as exc:
            log.error(f"  ❌ Broadcast error: {exc}", exc_info=True)

        return state

    return broadcast_node
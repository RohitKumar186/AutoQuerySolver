"""
worker6/nodes/memory_node.py
Step 3 — Feed confirmed fix pairs into ChromaDB for Worker 3's self-learning.
Only runs for fix events with fix_valid=True or confidence >= 0.7.
"""

import logging

log = logging.getLogger("MemoryNode")


def build_memory_node(memory_writer):
    def memory_node(state: dict) -> dict:
        if state.get("skipped"):
            return state

        if not state.get("is_fix_event"):
            log.info("  ⏭️  Clean record — memory write skipped.")
            return {**state, "memory_written": False}

        log.info("  🧠 Updating ChromaDB memory …")

        success = memory_writer.write({
            "record_id":   state.get("record_id"),
            "original":    state.get("original", {}),
            "fixed":       state.get("fixed", {}),
            "issues":      state.get("issues", []),
            "confidence":  state.get("confidence"),
            "fix_valid":   state.get("fix_valid"),
            "explanation": state.get("explanation", ""),
            "ts":          state.get("ts", ""),
        })

        log.info(f"  {'✅' if success else '⚠️ '} Memory write — success={success}")
        return {**state, "memory_written": success}

    return memory_node
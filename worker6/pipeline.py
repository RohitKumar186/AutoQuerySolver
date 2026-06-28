"""
worker6/pipeline.py
LangGraph state machine for Worker 6.

Flow:
  [ingest] → if skipped → END
           → [audit] → [memory] → [reporter] → [broadcast] → END
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Any

from nodes.ingest_node    import ingest_node
from nodes.audit_node     import build_audit_node
from nodes.memory_node    import build_memory_node
from nodes.reporter_node  import build_reporter_node
from nodes.broadcast_node import build_broadcast_node


class LoggerState(TypedDict):
    # Input
    raw_event:         dict

    # Parsed by ingest_node
    op:                str
    record_id:         Any
    original:          dict
    fixed:             dict
    before:            Any
    issues:            list
    confidence:        Any
    fix_valid:         bool
    approved_by:       Any
    explanation:       str
    worker:            str
    ts:                str
    is_fix_event:      bool
    skipped:           bool

    # Set by audit_node
    audit_id:          Any
    audit_row:         Any

    # Set by memory_node
    memory_written:    bool

    # Set by reporter_node
    dashboard_payload: Any
    full_report:       Any


def _route_after_ingest(state: LoggerState) -> str:
    return "skip" if state.get("skipped") else "audit"


def _skip_node(state: LoggerState) -> LoggerState:
    return state


def build_pipeline(audit_writer, memory_writer, report_builder, broadcast_fn):
    audit_node     = build_audit_node(audit_writer)
    memory_node    = build_memory_node(memory_writer)
    reporter_node  = build_reporter_node(audit_writer, report_builder)
    broadcast_node = build_broadcast_node(broadcast_fn)

    graph = StateGraph(LoggerState)

    graph.add_node("ingest",    ingest_node)
    graph.add_node("skip",      _skip_node)
    graph.add_node("audit",     audit_node)
    graph.add_node("memory",    memory_node)
    graph.add_node("reporter",  reporter_node)
    graph.add_node("broadcast", broadcast_node)

    graph.set_entry_point("ingest")

    graph.add_conditional_edges(
        "ingest",
        _route_after_ingest,
        {"skip": "skip", "audit": "audit"},
    )

    graph.add_edge("skip",      END)
    graph.add_edge("audit",     "memory")
    graph.add_edge("memory",    "reporter")
    graph.add_edge("reporter",  "broadcast")
    graph.add_edge("broadcast", END)

    return graph.compile()
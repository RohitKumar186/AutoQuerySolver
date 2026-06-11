"""
graph/pipeline.py
LangGraph pipeline for Worker 3.

Flow:
  [check_issues] → if clean → [skip]
                 → if issues → [embed] → [search] → [fixer] → [validator] → [saver]
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Any

from nodes.check_issues import check_issues_node
from issues.embed       import embed_node
from issues.search      import search_node
from issues.fixer       import fixer_node
from issues.validator   import validator_node
from issues.saver       import build_saver_node


class DoctorState(TypedDict):
    op:        str
    record:    dict
    before:    Any
    issues:    list
    embedding: list
    similar:   list
    fix:       Any
    fix_valid: bool
    skipped:   bool
    ts:        str


def route_after_check(state: DoctorState) -> str:
    if state.get("skipped"):
        return "skip"
    return "embed"


def route_after_validate(state: DoctorState) -> str:
    return "saver"


def skip_node(state: DoctorState) -> DoctorState:
    return {**state, "skipped": True}


def build_pipeline(broadcast_fn):
    saver_node = build_saver_node(broadcast_fn)

    graph = StateGraph(DoctorState)

    graph.add_node("check_issues", check_issues_node)
    graph.add_node("skip",         skip_node)
    graph.add_node("embed",        embed_node)
    graph.add_node("search",       search_node)
    graph.add_node("fixer",        fixer_node)
    graph.add_node("validator",    validator_node)
    graph.add_node("saver",        saver_node)

    graph.set_entry_point("check_issues")

    graph.add_conditional_edges(
        "check_issues",
        route_after_check,
        {"skip": "skip", "embed": "embed"}
    )

    graph.add_edge("skip",      END)
    graph.add_edge("embed",     "search")
    graph.add_edge("search",    "fixer")
    graph.add_edge("fixer",     "validator")

    graph.add_conditional_edges(
        "validator",
        route_after_validate,
        {"saver": "saver"}
    )

    graph.add_edge("saver", END)

    return graph.compile()
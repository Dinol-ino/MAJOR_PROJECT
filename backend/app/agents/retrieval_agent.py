"""Bounded agentic retrieval (LangGraph) for multi-part legal questions.

    plan -> retrieve -> assess -> (retry <= MAX_RETRIES) -> merge

The graph only decides WHAT to retrieve and whether coverage is sufficient. It never generates
text, never calls tools, and every chunk still flows through the same downstream sanitizer,
output validator, ownership checks and egress guard as the single-shot path. Planning is
deterministic (no model call), so a weak local model cannot steer retrieval, and the step count
is hard-capped. If langgraph is unavailable the same nodes run as a plain loop.
"""
import re
from typing import Any, Callable, Dict, List, TypedDict

MAX_SUBQUERIES = 4
MAX_RETRIES = 1

_ACT = r"(?:[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,5}\s+(?:Act|Code|Sanhita|Adhiniyam)(?:,?\s*\d{4})?|IPC|BNS|BNSS|CrPC|BSA|CPC)"
_SECTION_REF = re.compile(rf"(?i:\bsec(?:tion|\.)?)\s*(\d+[A-Za-z]{{0,3}})\s*(?:(?i:of)\s+(?:(?i:the)\s+)?)?({_ACT})?")
_SPLITTERS = re.compile(r"(?i)\s+(?:versus|vs\.?|compared\s+(?:to|with)|as\s+opposed\s+to)\s+|\s+and\s+also\s+|;\s+")


class AgentState(TypedDict, total=False):
    query: str
    subqueries: List[str]
    chunks: List[Dict[str, Any]]
    uncovered: List[str]
    retries: int
    steps: List[str]


def plan_subqueries(query: str) -> List[str]:
    q = " ".join(query.split())
    refs = []
    for m in _SECTION_REF.finditer(q):
        sec, act = m.group(1), (m.group(2) or "").strip()
        refs.append(f"Section {sec} {act}".strip())
    if len(refs) >= 2:
        return list(dict.fromkeys(refs))[:MAX_SUBQUERIES]
    parts = [p.strip(" ?.") for p in _SPLITTERS.split(q) if p and len(p.strip()) > 6]
    if len(parts) >= 2:
        return parts[:MAX_SUBQUERIES]
    qs = [p.strip() for p in re.split(r"\?\s+", q) if len(p.strip()) > 6]
    return qs[:MAX_SUBQUERIES] if len(qs) >= 2 else [q]


def _key(c: Dict[str, Any]):
    m = c.get("metadata") or {}
    return (str(c.get("act")), str(c.get("section")), str(m.get("doc_id") or c.get("doc_id") or ""),
            str(m.get("page_start") or ""), (c.get("text") or "")[:60])


def run(query: str, retrieve_fn: Callable[[str], List[Dict[str, Any]]],
        supports_fn: Callable[[str, List[Dict[str, Any]]], bool], max_chunks: int) -> AgentState:
    def plan(s: AgentState) -> AgentState:
        return {"subqueries": plan_subqueries(s["query"]), "chunks": [], "uncovered": [], "retries": 0,
                "steps": ["plan"]}

    def retrieve(s: AgentState) -> AgentState:
        targets = s["uncovered"] or s["subqueries"]
        chunks = list(s["chunks"])
        for sq in targets:
            chunks.extend(retrieve_fn(sq))
        return {"chunks": chunks, "steps": s["steps"] + ["retrieve"]}

    def assess(s: AgentState) -> AgentState:
        uncovered = [sq for sq in s["subqueries"] if not supports_fn(sq, s["chunks"])]
        return {"uncovered": uncovered, "retries": s["retries"] + (1 if s["uncovered"] else 0),
                "steps": s["steps"] + ["assess"]}

    def route(s: AgentState) -> str:
        return "retrieve" if s["uncovered"] and s["retries"] < MAX_RETRIES and s["uncovered"] != s.get("_last") else "merge"

    def merge(s: AgentState) -> AgentState:
        seen, out = set(), []
        # round-robin across sub-questions is approximated by original order; dedupe then cap
        for c in s["chunks"]:
            k = _key(c)
            if k not in seen:
                seen.add(k); out.append(c)
        return {"chunks": out[:max_chunks], "steps": s["steps"] + ["merge"]}

    init: AgentState = {"query": query}
    try:
        from langgraph.graph import END, StateGraph
        g = StateGraph(AgentState)
        for name, fn in (("plan", plan), ("retrieve", retrieve), ("assess", assess), ("merge", merge)):
            g.add_node(name, fn)
        g.set_entry_point("plan")
        g.add_edge("plan", "retrieve")
        g.add_edge("retrieve", "assess")
        g.add_conditional_edges("assess", route, {"retrieve": "retrieve", "merge": "merge"})
        g.add_edge("merge", END)
        return g.compile().invoke(init, {"recursion_limit": 12})
    except ImportError:
        s = {**init, **plan(init)}
        while True:
            s.update(retrieve(s)); s.update(assess(s))
            if route(s) == "merge":
                break
        s.update(merge(s))
        return s

"""Shared LangGraph state for FixLens."""

from __future__ import annotations

from typing import Any, TypedDict


class FixLensState(TypedDict, total=False):
    query: str
    plan: dict[str, Any]
    current_step: int
    iterations: int
    tool_results: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    critic: dict[str, Any]
    verification: dict[str, Any]
    final_answer: str
    status: str
    error: str


def initial_state(query: str) -> FixLensState:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string.")
    return {
        "query": query.strip(),
        "plan": {},
        "current_step": 0,
        "iterations": 0,
        "tool_results": [],
        "evidence": [],
        "critic": {},
        "verification": {},
        "final_answer": "",
        "status": "started",
        "error": "",
    }

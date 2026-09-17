"""
FixLens deterministic action router.

The router maps planner actions to registered callables. It never uses an
LLM to select or validate facts.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .state import FixLensState

ToolCallable = Callable[..., Any]


class ToolRouter:
    ALLOWED_ACTIONS = {
        "lookup_issue", "lookup_pr", "lookup_commit", "lookup_release",
        "retrieve_issue", "retrieve_release", "verify_version",
        "verify_citations",
    }

    def __init__(self, tools: Mapping[str, ToolCallable] | None = None) -> None:
        self.tools: dict[str, ToolCallable] = dict(tools or {})

    def register(self, action: str, tool: ToolCallable) -> None:
        if action not in self.ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported FixLens action: {action!r}")
        if not callable(tool):
            raise TypeError("tool must be callable.")
        self.tools[action] = tool

    def available_actions(self) -> list[str]:
        return sorted(self.tools)

    def missing_actions(self) -> list[str]:
        return sorted(self.ALLOWED_ACTIONS - self.tools.keys())

    def route(self, action: str) -> ToolCallable:
        if action not in self.ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported FixLens action: {action!r}")
        try:
            return self.tools[action]
        except KeyError as exc:
            raise KeyError(f"No tool registered for action {action!r}.") from exc

    def execute(
        self,
        action: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = dict(parameters or {})
        tool = self.route(action)
        try:
            result = tool(**params)
            return {
                "action": action,
                "parameters": params,
                "success": True,
                "result": result,
            }
        except Exception as exc:
            return {
                "action": action,
                "parameters": params,
                "success": False,
                "result": None,
                "error": f"{type(exc).__name__}: {exc}",
            }


def router_node(router: ToolRouter):
    """LangGraph node that executes one step at state['current_step']."""

    def _node(state: FixLensState) -> dict[str, Any]:
        plan = state.get("plan", {})
        steps = plan.get("steps", [])
        index = state.get("current_step", 0)

        if index >= len(steps):
            return {"status": "plan_exhausted"}

        step = steps[index]
        if hasattr(step, "model_dump"):
            step = step.model_dump()

        action = step.get("action")
        if action == "finish":
            return {"current_step": index + 1, "status": "plan_finished"}

        observation = router.execute(
            action,
            step.get("parameters", {}),
        )

        results = list(state.get("tool_results", []))
        results.append(observation)

        return {
            "tool_results": results,
            "current_step": index + 1,
            "status": "tool_executed",
        }

    return _node

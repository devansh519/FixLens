"""
FixLens Stage 6 graph.

Planner -> execute ALL planned actions -> evidence -> critic.
If the critic says more evidence is required, planner receives the accumulated
state and creates a new plan. A deterministic verifier produces the final
factual result.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .router import ToolRouter
from .state import FixLensState, initial_state


class FixLensGraph:
    def __init__(
        self,
        planner: Any,
        critic: Any,
        router: ToolRouter,
        verifier: Any,
        *,
        answer_builder: Callable[[FixLensState], str] | None = None,
        max_iterations: int = 8,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1.")
        self.planner = planner
        self.critic = critic
        self.router = router
        self.verifier = verifier
        self.answer_builder = answer_builder or self._default_answer
        self.max_iterations = max_iterations
        self._compiled = self._build_graph()

    @staticmethod
    def _dict(value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, dict):
            return value
        raise TypeError(f"Expected dict-like value, got {type(value).__name__}.")

    def _plan_node(self, state: FixLensState) -> dict[str, Any]:
        plan = self.planner.plan(state["query"], state=state)
        return {
            "plan": self._dict(plan),
            "current_step": 0,
            "iterations": state.get("iterations", 0) + 1,
            "status": "planned",
        }

    def _critic_node(self, state: FixLensState) -> dict[str, Any]:
        decision = self.critic.evaluate(
            state["query"],
            list(state.get("evidence", [])),
            plan=state.get("plan", {}),
        )
        return {
            "critic": self._dict(decision),
            "status": "critic_evaluated",
        }

    def _sync_evidence(self, state: FixLensState) -> dict[str, Any]:
        # Successful observations are preserved verbatim. No interpretation is
        # performed here.
        evidence = list(state.get("evidence", []))
        start = len(evidence)
        observations = state.get("tool_results", [])
        for observation in observations[start:]:
            if observation.get("success"):
                evidence.append(observation)
        return {"evidence": evidence}

    def _verify_node(self, state: FixLensState) -> dict[str, Any]:
        evidence = list(state.get("evidence", []))
        verify = getattr(self.verifier, "verify", None)
        if verify is None:
            raise TypeError("verifier must expose verify().")
        try:
            result = verify(state)
        except TypeError:
            result = verify(state["query"], evidence)
        return {"verification": self._dict(result), "status": "verified"}

    def _answer_node(self, state: FixLensState) -> dict[str, Any]:
        return {
            "final_answer": self.answer_builder(state),
            "status": "completed",
        }

    def _build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise RuntimeError(
                "langgraph is required to build the FixLens graph."
            ) from exc

        graph = StateGraph(FixLensState)
        graph.add_node("planner", self._plan_node)
        graph.add_node("router", self._router_node())
        graph.add_node("sync_evidence", self._sync_evidence)
        graph.add_node("critic", self._critic_node)
        graph.add_node("verifier", self._verify_node)
        graph.add_node("answer", self._answer_node)

        graph.add_edge(START, "planner")
        graph.add_edge("planner", "router")
        graph.add_edge("router", "sync_evidence")
        graph.add_edge("sync_evidence", "critic")

        def after_critic(state: FixLensState) -> str:
            if state.get("critic", {}).get("status") == "sufficient":
                return "verifier"
            if state.get("iterations", 0) >= self.max_iterations:
                return "verifier"
            return "planner"

        graph.add_conditional_edges(
            "critic",
            after_critic,
            {"verifier": "verifier", "planner": "planner"},
        )
        graph.add_edge("verifier", "answer")
        graph.add_edge("answer", END)
        return graph.compile()

    def _router_node(self):
        """Execute every step in the current plan before critic evaluation."""

        def _node(state: FixLensState) -> dict[str, Any]:
            plan = state.get("plan", {})
            steps = plan.get("steps", [])
            results = list(state.get("tool_results", []))
            index = state.get("current_step", 0)

            while index < len(steps):
                step = steps[index]
                if hasattr(step, "model_dump"):
                    step = step.model_dump()
                action = step.get("action")
                if action == "finish":
                    index += 1
                    break
                observation = self.router.execute(
                    action,
                    step.get("parameters", {}),
                )
                results.append(observation)
                index += 1

            return {
                "tool_results": results,
                "current_step": index,
                "status": "plan_executed",
            }

        return _node

    @property
    def compiled(self):
        return self._compiled

    def invoke(self, query: str) -> FixLensState:
        return self._compiled.invoke(initial_state(query))

    @staticmethod
    def _default_answer(state: FixLensState) -> str:
        verification = state.get("verification", {})
        if not verification:
            return "FixLens could not produce a verification result."
        status = verification.get("status", "unknown")
        reason = verification.get("reason", "")
        return f"Fix status: {status}. {reason}".strip()


def build_fixlens_graph(
    *,
    planner: Any,
    critic: Any,
    router: ToolRouter,
    verifier: Any,
    answer_builder: Callable[[FixLensState], str] | None = None,
    max_iterations: int = 8,
) -> FixLensGraph:
    return FixLensGraph(
        planner=planner,
        critic=critic,
        router=router,
        verifier=verifier,
        answer_builder=answer_builder,
        max_iterations=max_iterations,
    )

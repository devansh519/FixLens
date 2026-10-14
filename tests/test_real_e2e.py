"""Real-data end-to-end execution test for FixLens with timing diagnostics."""

from __future__ import annotations

import os
import re

import pytest

from src.agents.critic import Critic
from src.agents.planner import Planner
from src.pipeline.graph import build_fixlens_graph
from src.pipeline.state import initial_state
from src.pipeline.tool_registry import build_real_tool_registry
from src.verification.verifier import VerificationEngine

REAL_ISSUE_NUMBER = int(os.getenv("FIXLENS_REAL_ISSUE_NUMBER", "11151"))


def test_real_pydantic_issue_e2e():
    if not os.getenv("GROQ_API_KEY"):
        pytest.fail(
            "GROQ_API_KEY is not configured. "
            "Set it in the FixLens environment before running this real-data test."
        )

    query = (
        f"Was pydantic/pydantic issue #{REAL_ISSUE_NUMBER} fixed? "
        "If it was fixed, identify the PR, merge commit, release/version, "
        "and the evidence supporting each step."
    )

    registry = build_real_tool_registry(
        metadata_path="storage/metadata/issue_pr_version.json",
        retrieval_limit=5,
    )
    assert registry.is_complete(), (
        "Real FixLens tool registry is incomplete. "
        f"Missing actions: {registry.missing_actions()}"
    )

    router = registry.build_router()
    graph = build_fixlens_graph(
        planner=Planner(),
        critic=Critic(),
        router=router,
        verifier=VerificationEngine(),
        max_iterations=8,
    )

    result = initial_state(query)
    for event in graph.stream(query):
        for node, update in event.items():
            previous_tool_count = len(result.get("tool_results", []))
            previous_evidence_count = len(result.get("evidence", []))
            result.update(update)

            if node == "planner":
                actions = [
                    step.get("action")
                    for step in result.get("plan", {}).get("steps", [])
                ]
                print(
                    f"TRACE node=planner iteration={result.get('iterations')} "
                    f"actions={actions}",
                    flush=True,
                )
            elif node == "router":
                for observation in result.get("tool_results", [])[previous_tool_count:]:
                    error = observation.get("error", "")
                    error_type = (
                        error.split(":", 1)[0]
                        if isinstance(error, str) and error
                        else None
                    )
                    error_detail = error_type
                    if isinstance(error, str):
                        argument_error = re.search(
                            r"(?:unexpected keyword argument|missing required "
                            r"positional argument) ['\"]([^'\"]+)['\"]",
                            error,
                        )
                        if argument_error:
                            error_detail = (
                                f"{error_type}({argument_error.group(1)})"
                            )
                        elif "invalid literal for int()" in error:
                            error_detail = "ValueError(invalid_identifier)"
                    print(
                        "TRACE node=router "
                        f"iteration={result.get('iterations')} "
                        f"action={observation.get('action')} "
                        f"success={observation.get('success')} "
                        f"parameter_names={sorted(observation.get('parameters', {}).keys())} "
                        f"error={error_detail}",
                        flush=True,
                    )
                if result.get("no_progress"):
                    print(
                        "TRACE node=router no new tool action executed",
                        flush=True,
                    )
            elif node == "sync_evidence":
                added = result.get("evidence", [])[previous_evidence_count:]
                print(
                    "TRACE node=sync_evidence "
                    f"added={[item.get('action') for item in added]} "
                    f"total={len(result.get('evidence', []))} "
                    f"next={'verifier (no progress)' if result.get('no_progress') else 'critic'}",
                    flush=True,
                )
            elif node == "critic":
                decision = result.get("critic", {})
                if decision.get("status") == "sufficient":
                    next_node = "verifier"
                elif not decision.get("suggested_actions"):
                    next_node = "verifier (no actions available)"
                elif result.get("no_progress"):
                    next_node = "verifier (no progress)"
                elif result.get("iterations", 0) >= graph.max_iterations:
                    next_node = "verifier (iteration limit)"
                else:
                    next_node = "planner"
                print(
                    "TRACE node=critic "
                    f"iteration={result.get('iterations')} "
                    f"decision={decision.get('status')} "
                    "suggested_actions="
                    f"{[item.get('action') for item in decision.get('suggested_actions', [])]} "
                    f"next={next_node}",
                    flush=True,
                )
            elif node == "verifier":
                verification = result.get("verification", {})
                print(
                    "TRACE node=verifier "
                    f"status={verification.get('status')} "
                    f"issue_verified={verification.get('issue_verified')} "
                    f"pr_verified={verification.get('pr_verified')} "
                    f"issue_pr_relation_verified={verification.get('issue_pr_relation_verified')} "
                    f"pr_merged={verification.get('pr_merged')} "
                    f"commit_verified={verification.get('commit_verified')} "
                    f"release_verified={verification.get('release_verified')}",
                    flush=True,
                )
            elif node == "answer":
                print("TRACE node=answer terminal=true", flush=True)

    assert result["status"] == "completed"
    assert result["final_answer"].strip()

    assert result["plan"]
    assert result["plan"].get("steps")
    critic = result.get("critic", {})
    assert "suggested_actions" in critic
    if critic.get("suggested_actions"):
        for action in critic["suggested_actions"]:
            assert isinstance(action, dict)
            assert "action" in action
            assert "parameters" in action

    tool_results = result.get("tool_results", [])
    assert tool_results

    successful_tools = [
        observation for observation in tool_results
        if observation.get("success") is True
    ]
    assert successful_tools

    evidence = result.get("evidence", [])
    assert evidence

    critic = result.get("critic", {})
    assert critic.get("status") in {"sufficient", "insufficient"}
    assert critic.get("reason")

    verification = result.get("verification", {})
    assert verification
    assert verification.get("status") in {
        "FIXED",
        "NOT_VERIFIED",
        "INSUFFICIENT_EVIDENCE",
    }
    if verification.get("status") == "FIXED":
        assert verification.get("issue_pr_relation_verified") is True
    assert verification.get("reason")

    print(
        "\n=== FixLens REAL E2E RESULT === "
        f"iterations={result.get('iterations')} "
        f"tool_observations={len(tool_results)} "
        f"successful_tools={len(successful_tools)} "
        f"evidence_items={len(evidence)} "
        f"critic={critic.get('status')} "
        f"verification={verification.get('status')}"
    )

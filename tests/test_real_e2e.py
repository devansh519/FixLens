"""Real-data end-to-end execution test for FixLens with timing diagnostics."""

from __future__ import annotations

import os

import pytest

from src.agents.critic import Critic
from src.agents.planner import Planner
from src.pipeline.graph import build_fixlens_graph
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

    result = graph.invoke(query)

    print("\n\n=== FINAL PLAN ===")
    print(result.get("plan"))

    print("\n=== TOOL RESULTS ===")
    for i, observation in enumerate(result.get("tool_results", []), 1):
        print(f"\n--- TOOL {i} ---")
        print(observation)

    print("\n=== EVIDENCE ===")
    print(result.get("evidence"))

    print("\n=== CRITIC ===")
    print(result.get("critic"))

    print("\n=== VERIFICATION ===")
    print(result.get("verification"))

    assert result["status"] == "completed"
    assert result["final_answer"].strip()

    assert result["plan"]
    assert result["plan"].get("steps")

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
    assert verification.get("reason")

    print("\n=== FixLens REAL E2E RESULT ===")
    print(f"Query: {query}")
    print(f"Iterations: {result.get('iterations')}")
    print(f"Planner steps: {len(result['plan'].get('steps', []))}")
    print(f"Tool observations: {len(tool_results)}")
    print(f"Successful observations: {len(successful_tools)}")
    print(f"Evidence items: {len(evidence)}")
    print(f"Critic: {critic.get('status')} — {critic.get('reason')}")
    print(
        "Verification: "
        f"{verification.get('status')} — {verification.get('reason')}"
    )

    timings = result.get("timings", {})
    print("\n=== FixLens TIMING BREAKDOWN ===")
    for phase in (
        "planner",
        "router",
        "sync_evidence",
        "critic",
        "verification",
        "answer",
        "total",
    ):
        if phase in timings:
            print(f"{phase:<18} {timings[phase]:>9.3f}s")

    tool_timings = result.get("tool_timings", [])
    if tool_timings:
        print("\n=== TOOL TIMINGS ===")
        for item in tool_timings:
            print(
                f"iter={item['iteration']:<2} "
                f"{item['action']:<20} "
                f"{item['elapsed_seconds']:>9.3f}s"
            )

    print(f"\nFinal answer: {result['final_answer']}")

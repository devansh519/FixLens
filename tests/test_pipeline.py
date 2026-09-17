"""Integration-style tests for the Stage 5 FixLens graph.

These tests use fake Planner/Critic/Verifier components and a deterministic
router. No Groq, Qdrant, or network connection is required.
"""

from __future__ import annotations

from src.pipeline.graph import build_fixlens_graph
from src.pipeline.router import ToolRouter


class FakePlanner:
    def __init__(self):
        self.calls = 0

    def plan(self, query, *, state=None):
        self.calls += 1
        # First pass gathers issue/PR evidence. The second pass is deliberately
        # unused in the sufficient-evidence test.
        return {
            "goal": "Verify the issue fix.",
            "steps": [
                {
                    "action": "lookup_pr",
                    "reason": "Verify the linked PR.",
                    "parameters": {"issue_number": 11151},
                }
            ],
            "requires_verification": True,
        }


class FakeCritic:
    def __init__(self):
        self.calls = 0

    def evaluate(self, query, evidence, *, plan=None):
        self.calls += 1
        return {
            "status": "sufficient",
            "reason": "The merged PR evidence is sufficient for deterministic verification.",
            "missing_evidence": [],
            "suggested_actions": [],
        }


class FakeVerifier:
    def verify(self, state):
        return {
            "status": "FIXED",
            "reason": "Verified merged PR and merge commit.",
            "pr_verified": True,
            "pr_merged": True,
            "commit_verified": True,
            "release_verified": False,
        }


def test_pipeline_runs_planner_router_critic_verifier():
    planner = FakePlanner()
    critic = FakeCritic()

    router = ToolRouter({
        "lookup_pr": lambda issue_number: {
            "pull_request": {
                "number": 3552,
                "merged_at": "2021-12-24T13:11:06Z",
                "merge_commit_sha": "abc123",
            }
        }
    })

    graph = build_fixlens_graph(
        planner=planner,
        critic=critic,
        router=router,
        verifier=FakeVerifier(),
    )

    result = graph.invoke("Was issue #11151 fixed?")

    assert result["status"] == "completed"
    assert result["final_answer"]
    assert result["verification"]["status"] == "FIXED"
    assert result["tool_results"][0]["success"] is True
    assert planner.calls == 1
    assert critic.calls == 1

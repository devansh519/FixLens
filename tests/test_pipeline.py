"""Integration-style tests for the Stage 5 FixLens graph.

These tests use fake Planner/Critic/Verifier components and a deterministic
router. No Groq, Qdrant, or network connection is required.
"""

from __future__ import annotations

from src.pipeline.graph import build_fixlens_graph
from src.pipeline.router import ToolRouter
from src.verification.verifier import VerificationEngine


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


def test_pipeline_persists_only_new_successful_evidence_across_iterations():
    class IterativePlanner:
        def __init__(self):
            self.calls = 0

        def plan(self, query, *, state=None):
            self.calls += 1
            action = ("lookup_issue", "lookup_pr", "lookup_commit")[self.calls - 1]
            parameter = {
                "lookup_issue": {"issue_number": 11151},
                "lookup_pr": {"pr_number": 42},
                "lookup_commit": {"commit_sha": "abcdef1234567"},
            }[action]
            return {
                "goal": "Verify evidence.",
                "steps": [{
                    "action": action,
                    "reason": "Collect the next evidence record.",
                    "parameters": parameter,
                }],
                "requires_verification": True,
            }

    class IterativeCritic:
        def __init__(self):
            self.calls = 0
            self.evidence_counts = []

        def evaluate(self, query, evidence, *, plan=None):
            self.calls += 1
            self.evidence_counts.append(len(evidence))
            sufficient = self.calls == 3
            return {
                "status": "sufficient" if sufficient else "insufficient",
                "reason": "Enough evidence." if sufficient else "More evidence needed.",
                "missing_evidence": [] if sufficient else ["another record"],
                "suggested_actions": (
                    []
                    if sufficient
                    else [{
                        "action": "lookup_pr" if self.calls == 1 else "lookup_commit",
                        "parameters": (
                            {"pr_number": 42}
                            if self.calls == 1
                            else {"commit_sha": "abcdef1234567"}
                        ),
                    }]
                ),
            }

    planner = IterativePlanner()
    critic = IterativeCritic()
    graph = build_fixlens_graph(
        planner=planner,
        critic=critic,
        router=ToolRouter({
            "lookup_issue": lambda **_: (_ for _ in ()).throw(
                RuntimeError("temporary lookup failure")
            ),
            "lookup_pr": lambda **_: {"pull_request": {"number": 42}},
            "lookup_commit": lambda **_: {"commit": {"sha": "abcdef1234567"}},
        }),
        verifier=VerificationEngine(),
    )

    result = graph.invoke("Verify linked issue evidence.")

    assert result["status"] == "completed"
    assert critic.evidence_counts == [0, 1, 2]
    assert [item["action"] for item in result["evidence"]] == [
        "lookup_pr",
        "lookup_commit",
    ]
    assert len(result["evidence"]) == 2
    assert result["verification"]["tool_errors"] == [{
        "action": "lookup_issue",
        "parameters": {"issue_number": 11151},
        "error_type": "RuntimeError",
    }]


def test_repeated_action_proposal_terminates_as_unresolved():
    class RepeatingPlanner:
        def __init__(self):
            self.calls = 0

        def plan(self, query, *, state=None):
            self.calls += 1
            return {
                "goal": "Verify issue fix.",
                "steps": [{
                    "action": "lookup_issue",
                    "reason": "Look up the known issue.",
                    "parameters": {"issue_number": 11151},
                }],
                "requires_verification": True,
            }

    class InsufficientCritic:
        def __init__(self):
            self.calls = 0

        def evaluate(self, query, evidence, *, plan=None):
            self.calls += 1
            return {
                "status": "insufficient",
                "reason": "No fixing PR evidence is available.",
                "missing_evidence": ["verified fixing PR"],
                "suggested_actions": [{
                    "action": "lookup_issue",
                    "parameters": {"issue_number": 11151},
                }],
            }

    planner = RepeatingPlanner()
    critic = InsufficientCritic()
    calls = []
    graph = build_fixlens_graph(
        planner=planner,
        critic=critic,
        router=ToolRouter({
            "lookup_issue": lambda issue_number: calls.append(issue_number) or {
                "issue": {"number": issue_number, "state": "open"},
            }
        }),
        verifier=VerificationEngine(),
    )

    result = graph.invoke("Was issue #11151 fixed?")

    assert result["status"] == "completed"
    assert result["verification"]["status"] == "NOT_VERIFIED"
    assert result["critic"]["status"] == "insufficient"
    assert result["no_progress"] is True
    assert planner.calls == 2
    assert critic.calls == 1
    assert calls == [11151]
    assert len(result["tool_results"]) == 1
    assert "complete fix chain" in result["verification"]["reason"]


def test_failed_tool_ends_unresolved_and_is_not_evidence():
    class RepeatingPlanner:
        def __init__(self):
            self.calls = 0

        def plan(self, query, *, state=None):
            self.calls += 1
            return {
                "goal": "Verify issue fix.",
                "steps": [{
                    "action": "lookup_issue",
                    "reason": "Look up the issue.",
                    "parameters": {"issue_number": 11151},
                }],
                "requires_verification": True,
            }

    class InsufficientCritic:
        def evaluate(self, query, evidence, *, plan=None):
            return {
                "status": "insufficient",
                "reason": "Issue metadata is unavailable.",
                "missing_evidence": ["issue metadata"],
                "suggested_actions": [],
            }

    planner = RepeatingPlanner()
    graph = build_fixlens_graph(
        planner=planner,
        critic=InsufficientCritic(),
        router=ToolRouter({
            "lookup_issue": lambda **_: (_ for _ in ()).throw(
                ConnectionError("service unavailable")
            )
        }),
        verifier=VerificationEngine(),
    )

    result = graph.invoke("Was issue #11151 fixed?")

    assert result["status"] == "completed"
    assert result["verification"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["evidence"] == []
    assert result["tool_results"][0]["success"] is False
    assert result["verification"]["tool_errors"][0]["error_type"] == "ConnectionError"
    assert "tool call(s) failed" in result["verification"]["reason"]
    assert planner.calls == 1

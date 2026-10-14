"""Stage 6 end-to-end pipeline test using deterministic local doubles.

This validates the full Planner -> Router -> Critic -> Verifier -> Answer
flow without network calls. The separate integration tests validate the
registry seam; this test validates orchestration.
"""

from __future__ import annotations

from src.pipeline.graph import build_fixlens_graph
from src.pipeline.tool_registry import build_tool_registry
from src.verification.verifier import VerificationEngine


class FakePlanner:
    def plan(self, query, *, state=None):
        # A real planner will generate this dynamically. This deterministic
        # double lets the E2E test run without an LLM/API key.
        return {
            "goal": "Verify whether issue #11151 was fixed.",
            "steps": [
                {
                    "action": "lookup_issue",
                    "reason": "The issue number is known.",
                    "parameters": {"issue_number": 11151},
                },
                {
                    "action": "lookup_pr",
                    "reason": "Verify the associated PR.",
                    "parameters": {"pr_number": 3552},
                },
            ],
            "requires_verification": True,
        }


class FakeCritic:
    def evaluate(self, query, evidence, *, plan=None):
        return {
            "status": "sufficient",
            "reason": "Required issue and PR evidence is present.",
            "missing_evidence": [],
            "suggested_actions": [],
        }


class FakeMetadata:
    def get_by_issue_number(self, issue_number):
        return {
            "issue": {
                "number": issue_number,
                "title": "Example issue",
                "url": f"https://github.com/pydantic/pydantic/issues/{issue_number}",
            }
        }

    def get_by_pr_number(self, pr_number):
        return {
            "pull_request": {
                "number": pr_number,
                "state": "closed",
                "body": "Fixes #11151",
                "merged_at": "2021-12-24T13:11:06Z",
                "merge_commit_sha": "e14e123",
                "url": f"https://github.com/pydantic/pydantic/pull/{pr_number}",
            }
        }

    def get_by_commit_sha(self, commit_sha):
        return {"commit": {"sha": commit_sha}}

    def get_by_release_tag(self, release_tag):
        return {
            "version_info": {
                "release": None,
                "tag_name": None,
            }
        }


def test_real_stage6_pipeline_shape():
    metadata = FakeMetadata()

    registry = build_tool_registry(metadata_lookup=metadata)

    # Only the actions used by this E2E scenario need to be registered.
    assert "lookup_issue" not in registry.missing_actions()

    router = registry.build_router()

    graph = build_fixlens_graph(
        planner=FakePlanner(),
        critic=FakeCritic(),
        router=router,
        verifier=VerificationEngine(),
    )

    result = graph.invoke("Was issue #11151 fixed?")

    assert result["status"] == "completed"
    assert result["verification"]["status"] == "FIXED"
    assert result["verification"]["pr_merged"] is True
    assert result["verification"]["commit_verified"] is True
    assert result["verification"]["release_verified"] is False
    assert "verified merged fix" in result["final_answer"].lower()

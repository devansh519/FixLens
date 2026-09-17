"""Unit tests for the FixLens Stage 5 planner."""

from __future__ import annotations

import json

import pytest

from src.agents.planner import AnalysisPlan, Planner


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return FakeResponse(self.content)


def test_planner_returns_structured_plan():
    llm = FakeLLM(json.dumps({
        "goal": "Verify whether issue 11151 was fixed.",
        "steps": [
            {
                "action": "lookup_issue",
                "reason": "The issue number is known.",
                "parameters": {"issue_number": 11151},
            },
            {
                "action": "verify_citations",
                "reason": "Validate the collected evidence citations.",
                "parameters": {},
            },
        ],
        "requires_verification": True,
    }))

    plan = Planner(llm=llm).plan("Was issue #11151 fixed?")

    assert isinstance(plan, AnalysisPlan)
    assert plan.goal.startswith("Verify")
    assert plan.steps[0].action == "lookup_issue"
    assert plan.steps[0].parameters["issue_number"] == 11151
    assert len(llm.calls) == 1


def test_planner_passes_existing_state_to_llm():
    llm = FakeLLM(json.dumps({
        "goal": "Verify the release for issue 11151.",
        "steps": [
            {
                "action": "lookup_release",
                "reason": "The merged commit is already known.",
                "parameters": {"commit_sha": "abc123"},
            }
        ],
        "requires_verification": True,
    }))

    state = {"tool_results": [{"action": "lookup_issue", "success": True}]}
    plan = Planner(llm=llm).plan("Was issue #11151 released?", state=state)

    assert plan.steps[0].action == "lookup_release"
    human_message = llm.calls[0][1][1]
    payload = json.loads(human_message)
    assert payload["current_state"] == state


def test_planner_rejects_empty_query():
    planner = Planner(llm=FakeLLM("{}"))

    with pytest.raises(ValueError):
        planner.plan("   ")


def test_planner_rejects_invalid_llm_json():
    planner = Planner(llm=FakeLLM("not json"))

    with pytest.raises(ValueError):
        planner.plan("Was issue #1 fixed?")

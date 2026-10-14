"""Unit tests for the deterministic FixLens Stage 5 router."""

from __future__ import annotations

import pytest

from src.agents.critic import Critic
from src.pipeline.router import ToolRouter


def test_router_registers_and_executes_tool():
    calls = []

    def lookup_issue(issue_number: int):
        calls.append(issue_number)
        return {"issue": {"number": issue_number}}

    router = ToolRouter({"lookup_issue": lookup_issue})

    result = router.execute(
        "lookup_issue",
        {"issue_number": 11151},
    )

    assert result["success"] is True
    assert result["action"] == "lookup_issue"
    assert result["result"]["issue"]["number"] == 11151
    assert calls == [11151]


def test_router_rejects_unknown_action():
    router = ToolRouter()

    with pytest.raises(ValueError):
        router.route("invent_fact")


def test_router_reports_missing_tool():
    router = ToolRouter()

    with pytest.raises(KeyError):
        router.route("lookup_issue")


def test_router_converts_tool_exception_to_failed_observation():
    def broken_tool(**kwargs):
        raise RuntimeError("database unavailable")

    router = ToolRouter({"lookup_issue": broken_tool})

    result = router.execute("lookup_issue", {"issue_number": 1})

    assert result["success"] is False
    assert result["result"] is None
    assert "database unavailable" in result["error"]


def test_critic_structured_action_executes_with_router_contract():
    proposed = Critic._normalize_suggested_actions([{
        "action": "lookup_issue",
        "parameters": {"issue_number": 11151},
    }])
    calls = []
    router = ToolRouter({
        "lookup_issue": lambda issue_number: calls.append(issue_number) or {
            "issue": {"number": issue_number},
        }
    })

    assert len(proposed) == 1
    action = proposed[0]
    result = router.execute(action.action, action.parameters)

    assert result["success"] is True
    assert result["result"]["issue"]["number"] == 11151
    assert calls == [11151]


def test_critic_rejects_malformed_structured_action():
    proposed = Critic._normalize_suggested_actions([{
        "action": "lookup_issue",
        "parameters": {"issue_number": "<ISSUE_NUMBER>"},
    }])

    assert proposed == []

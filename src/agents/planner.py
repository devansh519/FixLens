"""FixLens LLM planner: decides which investigation action to take next."""

from __future__ import annotations

import json
import os
from typing import Any, Literal

from pydantic import BaseModel, Field

ActionType = Literal[
    "lookup_issue", "lookup_pr", "lookup_commit", "lookup_release",
    "retrieve_issue", "retrieve_release", "verify_version",
    "verify_citations", "finish",
]


class PlanStep(BaseModel):
    action: ActionType
    reason: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class AnalysisPlan(BaseModel):
    goal: str = Field(min_length=1)
    steps: list[PlanStep] = Field(default_factory=list)
    requires_verification: bool = True


SYSTEM_PROMPT = """You are the planning component of FixLens.
Decide WHAT should be investigated, never WHAT the factual answer is.

Available actions:
- lookup_issue: exact issue metadata lookup by issue_number; optional owner/repo
- lookup_pr: exact PR metadata lookup by pr_number; optional owner/repo
- lookup_commit: exact merge-commit lookup by commit_sha; optional owner/repo
- lookup_release: exact release/tag lookup by release_tag; optional owner/repo
- retrieve_issue: semantic retrieval by query; optional limit/owner/repo
- retrieve_release: semantic retrieval by query; optional limit/owner/repo
- verify_version: compare actual_version and required_version; optional operation
- verify_citations: validate supplied evidence or citations
- finish: stop planning when enough evidence exists

Rules:
1. Prefer exact lookup when an identifier is known.
2. Use retrieval when an identifier is unknown or more context is needed.
3. Never invent GitHub IDs, SHAs, releases, or versions.
4. Version and citation claims must be checked by deterministic tools.
5. Keep the plan minimal.
6. The deterministic verifier, not the LLM, decides factual truth.
7. Use only the parameters listed for the selected action; do not add fields.
Return JSON only."""


class Planner:
    def __init__(
        self,
        llm: Any | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        self.llm = llm
        self.model = model or os.getenv(
            "FIXLENS_PLANNER_MODEL", "openai/gpt-oss-120b"
        )
        self.temperature = temperature

    def _build_llm(self) -> Any:
        if self.llm is not None:
            return self.llm
        try:
            from langchain_groq import ChatGroq
        except ImportError as exc:
            raise RuntimeError(
                "langchain-groq is required, or inject an LLM into Planner(llm=...)."
            ) from exc
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured.")
        self.llm = ChatGroq(
            model=self.model, temperature=self.temperature, api_key=api_key
        )
        return self.llm

    @staticmethod
    def _content(response: Any) -> str:
        content = getattr(response, "content", response)
        if isinstance(content, list):
            return "".join(
                str(x.get("text", x)) if isinstance(x, dict) else str(x)
                for x in content
            )
        return str(content)

    @staticmethod
    def _json(text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = lines[1:] if lines and lines[0].startswith("```") else lines
            lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
            text = "\n".join(lines).strip()
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Planner response did not contain a JSON object.")
        try:
            result = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("Planner returned invalid JSON.") from exc
        if not isinstance(result, dict):
            raise TypeError("Planner response must be a JSON object.")
        return result

    def plan(
        self, query: str, *, state: dict[str, Any] | None = None
    ) -> AnalysisPlan:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string.")

        state = state or {}

        def _compact(value: Any, max_chars: int = 1400) -> str:
            try:
                rendered = json.dumps(value, default=str, ensure_ascii=False)
            except (TypeError, ValueError):
                rendered = str(value)
            return rendered if len(rendered) <= max_chars else rendered[:max_chars] + "...[truncated]"

        compact_results = []
        for item in state.get("tool_results", [])[-4:]:
            compact_results.append({
                "action": item.get("action"),
                "parameters": item.get("parameters", {}),
                "success": item.get("success", False),
                "result": _compact(item.get("result"), 700),
                "error": _compact(item.get("error"), 250),
            })

        compact_evidence = []
        for item in state.get("evidence", [])[-4:]:
            compact_evidence.append({
                "action": item.get("action"),
                "parameters": item.get("parameters", {}),
                "result": _compact(item.get("result"), 700),
            })

        critic = state.get("critic", {})
        compact_critic = {
            "status": critic.get("status") if isinstance(critic, dict) else None,
            "reason": _compact(critic.get("reason"), 700) if isinstance(critic, dict) else "",
            "missing_evidence": list(critic.get("missing_evidence", []))[:6] if isinstance(critic, dict) else [],
            "suggested_actions": list(critic.get("suggested_actions", []))[:3] if isinstance(critic, dict) else [],
        }

        payload = {
            "query": query.strip(),
            "current_state": {
                "iterations": state.get("iterations", 0),
                "tool_result_count": len(state.get("tool_results", [])),
                "evidence_count": len(state.get("evidence", [])),
            },
            "planning_context": {
                "iterations": state.get("iterations", 0),
                "evidence": compact_evidence,
                "recent_tool_results": compact_results,
                "critic": compact_critic,
            },
            "output_schema": {
                "goal": "verification goal",
                "steps": [
                    {
                        "action": "allowed action",
                        "reason": "why this is the smallest useful next action",
                        "parameters": "parameters matching the exact action schema",
                    }
                ],
                "requires_verification": True,
            },
        }

        response = self._build_llm().invoke([
            ("system", SYSTEM_PROMPT),
            ("human", json.dumps(payload, default=str)),
        ])
        return AnalysisPlan.model_validate(self._json(self._content(response)))


def create_planner(llm: Any | None = None, **kwargs: Any) -> Planner:
    return Planner(llm=llm, **kwargs)

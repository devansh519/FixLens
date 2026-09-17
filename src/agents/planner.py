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
- lookup_issue: exact issue metadata lookup
- lookup_pr: exact PR metadata lookup
- lookup_commit: exact merge-commit lookup
- lookup_release: exact release/tag lookup
- retrieve_issue: semantic issue/PR retrieval
- retrieve_release: semantic release retrieval
- verify_version: deterministic semantic-version comparison
- verify_citations: deterministic citation validation
- finish: stop planning when enough evidence exists

Rules:
1. Prefer exact lookup when an identifier is known.
2. Use retrieval when an identifier is unknown or more context is needed.
3. Never invent GitHub IDs, SHAs, releases, or versions.
4. Version and citation claims must be checked by deterministic tools.
5. Keep the plan minimal.
6. The deterministic verifier, not the LLM, decides factual truth.
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
            "FIXLENS_PLANNER_MODEL", "llama-3.3-70b-versatile"
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
            raise ValueError("Planner response must be a JSON object.")
        return result

    def plan(
        self, query: str, *, state: dict[str, Any] | None = None
    ) -> AnalysisPlan:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string.")

        payload = {
            "query": query.strip(),
            "current_state": state or {},
            "output_schema": {
                "goal": "verification goal",
                "steps": [
                    {"action": "allowed action", "reason": "why", "parameters": {}}
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

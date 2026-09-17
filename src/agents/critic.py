"""FixLens evidence critic: checks whether evidence is sufficient for verification."""

from __future__ import annotations

import json
import os
from typing import Any, Literal

from pydantic import BaseModel, Field


class CriticDecision(BaseModel):
    status: Literal["sufficient", "insufficient"]
    reason: str = Field(min_length=1)
    missing_evidence: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = """You are the evidence critic for FixLens.
Assess whether CURRENT evidence is sufficient for deterministic verification.

Typical chain:
Issue -> PR -> merged commit -> release/tag -> requested version condition.

You do NOT establish facts. Only identify evidence that is present or missing.
A null/missing release or tag means the release is unverified.
Do not claim that a PR is merged or a commit is in a release unless supplied
evidence explicitly shows it.
Request only the smallest useful next actions.
Allowed actions:
lookup_issue, lookup_pr, lookup_commit, lookup_release,
retrieve_issue, retrieve_release, verify_version, verify_citations
Return JSON only."""


class Critic:
    def __init__(
        self,
        llm: Any | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        self.llm = llm
        self.model = model or os.getenv(
            "FIXLENS_CRITIC_MODEL", "llama-3.3-70b-versatile"
        )
        self.temperature = temperature

    def _build_llm(self) -> Any:
        if self.llm is not None:
            return self.llm
        try:
            from langchain_groq import ChatGroq
        except ImportError as exc:
            raise RuntimeError(
                "langchain-groq is required, or inject an LLM into Critic(llm=...)."
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
            raise ValueError("Critic response did not contain a JSON object.")
        try:
            result = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("Critic returned invalid JSON.") from exc
        if not isinstance(result, dict):
            raise ValueError("Critic response must be a JSON object.")
        return result

    def evaluate(
        self,
        query: str,
        evidence: dict[str, Any] | list[Any],
        *,
        plan: dict[str, Any] | None = None,
    ) -> CriticDecision:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string.")

        payload = {
            "query": query.strip(),
            "plan": plan or {},
            "evidence": evidence,
            "output_schema": {
                "status": "sufficient or insufficient",
                "reason": "why",
                "missing_evidence": [],
                "suggested_actions": [],
            },
        }

        response = self._build_llm().invoke([
            ("system", SYSTEM_PROMPT),
            ("human", json.dumps(payload, default=str)),
        ])
        return CriticDecision.model_validate(self._json(self._content(response)))

    def is_sufficient(
        self,
        query: str,
        evidence: dict[str, Any] | list[Any],
        *,
        plan: dict[str, Any] | None = None,
    ) -> bool:
        return self.evaluate(query, evidence, plan=plan).status == "sufficient"


def create_critic(llm: Any | None = None, **kwargs: Any) -> Critic:
    return Critic(llm=llm, **kwargs)

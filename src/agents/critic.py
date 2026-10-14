"""FixLens evidence critic: checks whether evidence is sufficient for verification."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from src.pipeline.router import ToolRouter

logger = logging.getLogger(__name__)

_ALLOWED_ACTIONS = frozenset(ToolRouter.ALLOWED_ACTIONS)
_REQUIRED_PARAMETERS = {
    "lookup_issue": {"issue_number"},
    "lookup_pr": {"pr_number"},
    "lookup_commit": {"commit_sha"},
    "lookup_release": {"release_tag"},
    "retrieve_issue": {"query"},
    "retrieve_release": {"query"},
    "verify_version": {"actual_version", "required_version"},
    "verify_citations": set(),
    "finish": set(),
}


class SuggestedAction(BaseModel):
    """Structured action proposal returned by the critic."""

    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("action")
    @classmethod
    def validate_action_name(cls, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("action must be a string.")
        candidate = value.strip()
        if not candidate:
            raise ValueError("action must not be empty.")
        if candidate not in _ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported FixLens action: {candidate!r}")
        return candidate

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise TypeError("parameters must be a dictionary.")
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            sanitized[str(key)] = item
        return sanitized

    @model_validator(mode="after")
    def validate_parameter_contract(self) -> SuggestedAction:
        required = _REQUIRED_PARAMETERS.get(self.action, set())
        missing = sorted(required - self.parameters.keys())
        if missing:
            raise ValueError(
                f"Action {self.action!r} is missing required parameters: "
                f"{', '.join(missing)}"
            )

        for key, value in self.parameters.items():
            if key in {"owner", "repo"}:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{key} must be a non-empty string.")
                if "<" in value or ">" in value:
                    raise ValueError(f"{key} contains a placeholder.")
                continue
            if value is None:
                continue
            if self.action in {"lookup_issue", "lookup_pr"}:
                if key in {"issue_number", "pr_number"}:
                    if isinstance(value, bool):
                        raise ValueError(f"{key} must be an integer or numeric string.")
                    if isinstance(value, int):
                        continue
                    if isinstance(value, str) and value.strip().isdigit():
                        continue
                    raise ValueError(f"{key} must be a positive integer value.")
            elif self.action == "lookup_commit":
                if key == "commit_sha":
                    if isinstance(value, str):
                        candidate = value.strip()
                        if not candidate or re.fullmatch(r"[0-9a-fA-F]{7,40}", candidate):
                            continue
                        raise ValueError("commit_sha must be a valid hexadecimal SHA.")
                    raise ValueError("commit_sha must be a string.")
            elif self.action == "lookup_release":
                if key == "release_tag":
                    if not isinstance(value, str):
                        raise ValueError("release_tag must be a string.")
                    candidate = value.strip()
                    if not candidate or "<" in candidate or ">" in candidate:
                        raise ValueError("release_tag contains a placeholder or is empty.")
            elif self.action in {"retrieve_issue", "retrieve_release"}:
                if key == "query":
                    if not isinstance(value, str):
                        raise ValueError("query must be a string.")
                    if not value.strip() or "<" in value or ">" in value:
                        raise ValueError("query must be a non-placeholder string.")
            elif (
                self.action == "verify_version"
                and key in {"actual_version", "required_version"}
            ):
                if not isinstance(value, str):
                    raise ValueError(f"{key} must be a string.")
                candidate = value.strip()
                if not candidate or "<" in candidate or ">" in candidate:
                    raise ValueError(f"{key} contains a placeholder or is empty.")
        return self


class CriticDecision(BaseModel):
    status: Literal["sufficient", "insufficient"]
    reason: str = Field(min_length=1)
    missing_evidence: list[str] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)


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
Return JSON in this shape:
{
  "status": "sufficient or insufficient",
  "reason": "why",
  "missing_evidence": ["..."],
  "suggested_actions": [
    {"action": "lookup_issue", "parameters": {"issue_number": 11151}}
  ]
}
Never return bare strings in suggested_actions.
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
            "FIXLENS_CRITIC_MODEL", "openai/gpt-oss-120b"
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
            raise TypeError("Critic response must be a JSON object.")
        return result

    @staticmethod
    def _normalize_suggested_actions(value: Any) -> list[SuggestedAction]:
        if value is None:
            return []
        if isinstance(value, list):
            actions: list[SuggestedAction] = []
            for item in value:
                if isinstance(item, SuggestedAction):
                    actions.append(item)
                elif isinstance(item, dict):
                    try:
                        actions.append(SuggestedAction.model_validate(item))
                    except ValidationError as exc:
                        logger.warning(
                            "Ignoring malformed critic action (%s).",
                            type(exc).__name__,
                        )
                        continue
                else:
                    continue
            return actions
        return []

    def evaluate(
        self,
        query: str,
        evidence: dict[str, Any] | list[Any],
        *,
        plan: dict[str, Any] | None = None,
    ) -> CriticDecision:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string.")

        def _compact(value: Any, max_chars: int = 1600) -> str:
            try:
                rendered = json.dumps(value, default=str, ensure_ascii=False)
            except (TypeError, ValueError):
                rendered = str(value)
            return rendered if len(rendered) <= max_chars else rendered[:max_chars] + "...[truncated]"

        compact_evidence = []
        for item in list(evidence)[-3:]:
            if isinstance(item, dict):
                compact_evidence.append({
                    "action": item.get("action"),
                    "parameters": item.get("parameters", {}),
                    "success": item.get("success", False),
                    "result": _compact(item.get("result"), 800),
                    "error": _compact(item.get("error"), 200),
                })
            else:
                compact_evidence.append(_compact(item))

        raw_plan = plan or {}
        compact_plan = {
            "goal": raw_plan.get("goal", "") if isinstance(raw_plan, dict) else "",
            "requires_verification": (
                raw_plan.get("requires_verification", True)
                if isinstance(raw_plan, dict) else True
            ),
            "steps": (
                list(raw_plan.get("steps", []))[-3:]
                if isinstance(raw_plan, dict) else []
            ),
        }

        payload = {
            "query": query.strip(),
            "plan": compact_plan,
            "evidence": compact_evidence,
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
        raw = self._json(self._content(response))
        if "suggested_actions" in raw:
            raw["suggested_actions"] = self._normalize_suggested_actions(raw["suggested_actions"])
        else:
            raw["suggested_actions"] = []
        try:
            return CriticDecision.model_validate(raw)
        except ValidationError:
            fallback = {
                "status": "insufficient",
                "reason": "The critic response was malformed; no safe action plan could be validated.",
                "missing_evidence": [
                    "A valid structured suggested_actions payload"
                ],
                "suggested_actions": [],
            }
            return CriticDecision.model_validate(fallback)

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

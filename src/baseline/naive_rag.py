"""Direct semantic-retrieval baseline without planner/critic iteration."""

from __future__ import annotations

from typing import Any

from src.pipeline.router import ToolRouter
from src.verification.verifier import VerificationEngine


class NaiveRAGBaseline:
    """Retrieve once, then apply the same deterministic verifier as FixLens."""

    def __init__(
        self,
        router: ToolRouter,
        verifier: VerificationEngine | None = None,
    ) -> None:
        self.router = router
        self.verifier = verifier or VerificationEngine()

    def run(self, query: str, *, owner: str, repo: str) -> dict[str, Any]:
        observation = self.router.execute(
            "retrieve_issue",
            {"query": query, "owner": owner, "repo": repo},
        )
        evidence = [observation] if observation.get("success") else []
        state = {
            "query": query,
            "tool_results": [observation],
            "evidence": evidence,
        }
        verification = self.verifier.verify(state)
        return {
            "verification": verification.model_dump(),
            "tool_results": [observation],
            "iterations": 1,
        }
"""
FixLens deterministic verification engine.

This module is intentionally independent from the LLM planner/critic.
It evaluates facts already returned by deterministic tools and applies
conservative rules to the Issue -> PR -> Merge Commit -> Release chain.

Important:
    Missing release/tag evidence is treated as UNKNOWN, not as "not released".
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VerificationResult(BaseModel):
    """Final factual verification produced by FixLens."""

    status: str
    reason: str
    issue_verified: bool = False
    pr_verified: bool = False
    pr_merged: bool = False
    commit_verified: bool = False
    release_verified: bool = False
    version_verified: bool = False
    citations_verified: bool = False
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class VerificationEngine:
    """
    Deterministic verifier for FixLens.

    The engine consumes normalized tool observations from the Stage 5 graph.
    It does not call an LLM and does not infer missing facts.
    """

    def verify(
        self,
        state_or_query: Any,
        evidence: list[dict[str, Any]] | None = None,
    ) -> VerificationResult:
        if isinstance(state_or_query, dict):
            state = state_or_query
            evidence_items = list(
                state.get("evidence", [])
                or state.get("tool_results", [])
            )
            if evidence is not None:
                evidence_items = list(evidence)
        else:
            evidence_items = list(evidence or [])

        flat = self._flatten_observations(evidence_items)

        issue = self._first_record(flat, "issue")
        pr = self._first_record(flat, "pull_request", "pr")
        commit = self._first_record(flat, "commit", "merge_commit")
        release = self._first_record(flat, "release", "version_info")
        citation = self._first_record(flat, "citation", "citations")

        issue_verified = issue is not None
        pr_verified = pr is not None

        pr_merged = self._merged(pr)
        commit_sha = self._commit_sha(pr, commit)
        commit_verified = bool(commit_sha)

        release_verified = self._release_verified(release, commit_sha)
        version_verified = self._version_verified(flat)
        citations_verified = self._citations_verified(flat, citation)

        # Conservative status semantics:
        # FIXED only requires a verified merged PR/commit. Release/version
        # claims are separately represented and never fabricated.
        if pr_merged and commit_verified:
            status = "FIXED"
            if release_verified:
                reason = "The issue has a verified merged fix and release evidence."
            else:
                reason = (
                    "The issue has a verified merged fix, but release evidence "
                    "could not be verified."
                )
        elif pr_verified and not pr_merged:
            status = "NOT_VERIFIED"
            reason = "A related pull request was found, but its merge is not verified."
        elif issue_verified:
            status = "NOT_VERIFIED"
            reason = (
                "The issue was found, but FixLens does not have enough verified "
                "evidence to establish the complete fix chain."
            )
        else:
            status = "INSUFFICIENT_EVIDENCE"
            reason = "FixLens could not verify the required GitHub evidence."

        return VerificationResult(
            status=status,
            reason=reason,
            issue_verified=issue_verified,
            pr_verified=pr_verified,
            pr_merged=pr_merged,
            commit_verified=commit_verified,
            release_verified=release_verified,
            version_verified=version_verified,
            citations_verified=citations_verified,
            evidence=evidence_items,
        )

    @staticmethod
    def _flatten_observations(observations: list[Any]) -> list[Any]:
        """Collect nested result objects without interpreting their facts."""
        output: list[Any] = []

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                output.append(value)
                for key in ("result", "data", "record", "records", "evidence"):
                    if key in value:
                        visit(value[key])
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        for item in observations:
            visit(item)
        return output

    @staticmethod
    def _first_record(items: list[Any], *keys: str) -> dict[str, Any] | None:
        for item in items:
            if not isinstance(item, dict):
                continue
            lowered = {str(k).lower(): v for k, v in item.items()}
            for key in keys:
                if key in lowered and isinstance(lowered[key], dict):
                    return lowered[key]
        return None

    @staticmethod
    def _merged(pr: dict[str, Any] | None) -> bool:
        if not pr:
            return False

        merged_at = pr.get("merged_at")
        if merged_at:
            return True

        merged = pr.get("merged")
        if isinstance(merged, bool):
            return merged

        state = str(pr.get("state", "")).lower()
        return state == "merged"

    @staticmethod
    def _commit_sha(
        pr: dict[str, Any] | None,
        commit: dict[str, Any] | None,
    ) -> str | None:
        for record in (pr, commit):
            if not record:
                continue
            for key in (
                "merge_commit_sha",
                "commit_sha",
                "sha",
                "merge_commit",
            ):
                value = record.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    @staticmethod
    def _release_verified(
        release: dict[str, Any] | None,
        commit_sha: str | None,
    ) -> bool:
        if not release:
            return False

        # Explicit null release/tag means missing evidence.
        release_value = release.get("release")
        tag = release.get("tag_name") or release.get("tag")

        if release_value is None and tag is None:
            return False

        # If the evidence explicitly associates the release with the merge
        # commit, accept it. Otherwise a release record alone is insufficient
        # to claim that this particular fix shipped in that release.
        associated_sha = (
            release.get("merge_commit_sha")
            or release.get("commit_sha")
            or release.get("sha")
        )
        if commit_sha and associated_sha:
            return associated_sha == commit_sha

        explicit = release.get("verified")
        return explicit is True

    @staticmethod
    def _version_verified(items: list[Any]) -> bool:
        for item in items:
            if not isinstance(item, dict):
                continue
            action = item.get("action")
            if action == "verify_version" and item.get("success") is True:
                result = item.get("result")
                if isinstance(result, bool):
                    return result
                if isinstance(result, dict):
                    if isinstance(result.get("valid"), bool):
                        return result["valid"]
                    if isinstance(result.get("satisfies"), bool):
                        return result["satisfies"]
        return False

    @staticmethod
    def _citations_verified(
        items: list[Any],
        citation: dict[str, Any] | None,
    ) -> bool:
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("action") == "verify_citations":
                if item.get("success") is not True:
                    continue
                result = item.get("result")
                if isinstance(result, bool):
                    return result
                if isinstance(result, dict):
                    if isinstance(result.get("valid"), bool):
                        return result["valid"]
                    if isinstance(result.get("verified"), bool):
                        return result["verified"]

        if citation:
            if isinstance(citation.get("valid"), bool):
                return citation["valid"]
            if isinstance(citation.get("verified"), bool):
                return citation["verified"]

        return False


def create_verifier() -> VerificationEngine:
    """Factory for the API/pipeline layer."""
    return VerificationEngine()

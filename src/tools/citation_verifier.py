from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse


class CitationVerifier:
    """Validate that generated answers contain usable evidence citations."""

    REQUIRED_KEYS = {
        "source",
        "source_type",
        "record_id",
    }

    @staticmethod
    def has_citations(answer: str) -> bool:
        """Check whether an answer contains at least one citation marker."""
        if not isinstance(answer, str):
            return False

        citation_markers = (
            "[source:",
            "[citation:",
            "github.com/",
            "https://github.com/",
        )

        normalized = answer.lower()

        return any(marker in normalized for marker in citation_markers)

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate that a URL is HTTP or HTTPS."""
        if not isinstance(url, str):
            return False

        try:
            parsed = urlparse(url)
        except ValueError:
            return False

        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @classmethod
    def validate_citation(
        cls,
        citation: dict[str, Any],
    ) -> bool:
        """
        Validate a structured citation.

        Expected structure:

        {
            "source": "https://github.com/pydantic/pydantic/issues/123",
            "source_type": "issue",
            "record_id": "issue-123"
        }
        """
        if not isinstance(citation, dict):
            return False

        if not cls.REQUIRED_KEYS.issubset(citation):
            return False

        if not all(citation[key] for key in cls.REQUIRED_KEYS):
            return False

        source = citation["source"]

        if isinstance(source, str) and cls.validate_url(source):
            return True

        return False

    @classmethod
    def validate_citations(
        cls,
        citations: Iterable[dict[str, Any]],
    ) -> bool:
        """Return True only when all supplied citations are valid."""
        citations = list(citations)

        if not citations:
            return False

        return all(cls.validate_citation(citation) for citation in citations)

    @classmethod
    def verify_evidence_block(
        cls,
        evidence: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Validate an evidence block and return a deterministic result.
        """
        if not isinstance(evidence, dict):
            return {
                "valid": False,
                "reason": "Evidence block is missing or invalid.",
            }

        citations = evidence.get("citations", [])

        if not cls.validate_citations(citations):
            return {
                "valid": False,
                "reason": "Evidence contains no valid citations.",
            }

        return {
            "valid": True,
            "reason": "Evidence citations are valid.",
            "citation_count": len(citations),
        }
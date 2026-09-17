import json
from pathlib import Path

import pytest

from src.tools.citation_verifier import CitationVerifier
from src.tools.metadata_lookup import MetadataLookup
from src.tools.version_verifier import (
    SemanticVersion,
    VersionVerifier,
)


@pytest.fixture
def metadata_file(tmp_path: Path) -> Path:
    """
    Create test metadata using the same nested schema as the real
    storage/metadata/issue_pr_version.json file.

    JSONL format is used here to verify that MetadataLookup supports
    line-by-line JSON records.
    """
    path = tmp_path / "metadata.jsonl"

    records = [
        {
            "issue": {
                "number": 123,
                "title": "Example issue",
                "body": "Example issue body",
                "state": "closed",
                "url": "https://github.com/example/repo/issues/123",
                "comments": [],
            },
            "pull_request": {
                "number": 999,
                "title": "Fix example issue",
                "body": "Example pull request body",
                "state": "closed",
                "merged_at": "2024-01-01T12:00:00Z",
                "merge_commit_sha": "ABC123",
                "url": "https://github.com/example/repo/pull/999",
            },
            "version_info": {
                "release": {
                    "name": "v2.6.0",
                },
                "tag_name": "v2.6.0",
            },
            "evidence": {
                "issue_url": "https://github.com/example/repo/issues/123",
                "pr_url": "https://github.com/example/repo/pull/999",
                "merge_commit_sha": "ABC123",
            },
        },
        {
            "issue": {
                "number": 456,
                "title": "Unresolved issue",
                "body": "Issue without release evidence",
                "state": "open",
                "url": "https://github.com/example/repo/issues/456",
                "comments": [],
            },
            "pull_request": {
                "number": 1000,
                "title": "Partial fix",
                "body": "Pull request without release information",
                "state": "closed",
                "merged_at": "2024-02-01T12:00:00Z",
                "merge_commit_sha": "DEF456",
                "url": "https://github.com/example/repo/pull/1000",
            },
            "version_info": {
                "release": None,
                "tag_name": None,
            },
            "evidence": {
                "issue_url": "https://github.com/example/repo/issues/456",
                "pr_url": "https://github.com/example/repo/pull/1000",
                "merge_commit_sha": "DEF456",
            },
        },
    ]

    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record) + "\n")

    return path


# ---------------------------------------------------------------------------
# MetadataLookup tests
# ---------------------------------------------------------------------------


def test_metadata_lookup_by_issue_number(
    metadata_file: Path,
) -> None:
    lookup = MetadataLookup(metadata_file)

    results = lookup.get_by_issue_number(123)

    assert len(results) == 1
    assert results[0]["issue"]["number"] == 123
    assert results[0]["pull_request"]["number"] == 999


def test_metadata_lookup_by_pr_number(
    metadata_file: Path,
) -> None:
    lookup = MetadataLookup(metadata_file)

    results = lookup.get_by_pr_number(999)

    assert len(results) == 1
    assert results[0]["pull_request"]["number"] == 999
    assert results[0]["issue"]["number"] == 123


def test_metadata_lookup_by_commit_sha(
    metadata_file: Path,
) -> None:
    lookup = MetadataLookup(metadata_file)

    results = lookup.get_by_commit_sha("ABC123")

    assert len(results) == 1
    assert results[0]["pull_request"]["merge_commit_sha"] == "ABC123"
    assert results[0]["evidence"]["merge_commit_sha"] == "ABC123"


def test_metadata_lookup_by_release_tag(
    metadata_file: Path,
) -> None:
    lookup = MetadataLookup(metadata_file)

    results = lookup.get_by_release_tag("v2.6.0")

    assert len(results) == 1
    assert results[0]["version_info"]["tag_name"] == "v2.6.0"


def test_metadata_lookup_returns_empty_for_unknown_issue(
    metadata_file: Path,
) -> None:
    lookup = MetadataLookup(metadata_file)

    results = lookup.get_by_issue_number(99999)

    assert results == []


def test_metadata_lookup_returns_empty_for_unknown_pr(
    metadata_file: Path,
) -> None:
    lookup = MetadataLookup(metadata_file)

    results = lookup.get_by_pr_number(99999)

    assert results == []


def test_metadata_lookup_returns_empty_for_unknown_commit(
    metadata_file: Path,
) -> None:
    lookup = MetadataLookup(metadata_file)

    results = lookup.get_by_commit_sha("UNKNOWN_SHA")

    assert results == []


def test_metadata_lookup_returns_empty_for_unknown_release(
    metadata_file: Path,
) -> None:
    lookup = MetadataLookup(metadata_file)

    results = lookup.get_by_release_tag("v9.9.9")

    assert results == []


def test_metadata_lookup_by_issue_and_pr(
    metadata_file: Path,
) -> None:
    lookup = MetadataLookup(metadata_file)

    results = lookup.get_by_issue_and_pr(
        issue_number=123,
        pr_number=999,
    )

    assert len(results) == 1
    assert results[0]["issue"]["number"] == 123
    assert results[0]["pull_request"]["number"] == 999


def test_metadata_lookup_issue_and_pr_mismatch(
    metadata_file: Path,
) -> None:
    lookup = MetadataLookup(metadata_file)

    results = lookup.get_by_issue_and_pr(
        issue_number=123,
        pr_number=1000,
    )

    assert results == []


def test_metadata_lookup_linked_evidence(
    metadata_file: Path,
) -> None:
    lookup = MetadataLookup(metadata_file)

    result = lookup.get_linked_evidence(123)

    assert result is not None
    assert result["issue"]["number"] == 123
    assert result["pull_request"]["number"] == 999
    assert result["pull_request"]["merge_commit_sha"] == "ABC123"
    assert result["version_info"]["tag_name"] == "v2.6.0"


def test_metadata_lookup_linked_evidence_for_unknown_issue(
    metadata_file: Path,
) -> None:
    lookup = MetadataLookup(metadata_file)

    result = lookup.get_linked_evidence(99999)

    assert result is None


def test_metadata_lookup_allows_missing_release_information(
    metadata_file: Path,
) -> None:
    lookup = MetadataLookup(metadata_file)

    results = lookup.get_by_issue_number(456)

    assert len(results) == 1
    assert results[0]["version_info"]["release"] is None
    assert results[0]["version_info"]["tag_name"] is None


# ---------------------------------------------------------------------------
# SemanticVersion and VersionVerifier tests
# ---------------------------------------------------------------------------


def test_semantic_version_parsing() -> None:
    version = SemanticVersion.parse("v2.6.0")

    assert version.major == 2
    assert version.minor == 6
    assert version.patch == 0


def test_semantic_version_parsing_without_v_prefix() -> None:
    version = SemanticVersion.parse("2.6.0")

    assert version.major == 2
    assert version.minor == 6
    assert version.patch == 0


def test_semantic_version_comparison() -> None:
    first = SemanticVersion.parse("2.5.0")
    second = SemanticVersion.parse("2.6.0")

    assert first < second
    assert second > first
    assert first != second


def test_semantic_version_equal_versions() -> None:
    first = SemanticVersion.parse("v2.6.0")
    second = SemanticVersion.parse("2.6.0")

    assert first == second


def test_version_is_at_least() -> None:
    verifier = VersionVerifier()

    assert verifier.is_at_least("v2.6.0", "v2.5.0") is True
    assert verifier.is_at_least("v2.6.0", "v2.6.0") is True
    assert verifier.is_at_least("v2.5.0", "v2.6.0") is False


def test_version_is_between() -> None:
    verifier = VersionVerifier()

    assert verifier.is_between(
        "v2.6.0",
        "v2.5.0",
        "v2.7.0",
    ) is True

    assert verifier.is_between(
        "v2.4.0",
        "v2.5.0",
        "v2.7.0",
    ) is False

    assert verifier.is_between(
        "v2.8.0",
        "v2.5.0",
        "v2.7.0",
    ) is False


def test_version_is_between_inclusive_boundaries() -> None:
    verifier = VersionVerifier()

    assert verifier.is_between(
        "v2.5.0",
        "v2.5.0",
        "v2.7.0",
    ) is True

    assert verifier.is_between(
        "v2.7.0",
        "v2.5.0",
        "v2.7.0",
    ) is True


def test_invalid_semantic_version() -> None:
    with pytest.raises(ValueError):
        SemanticVersion.parse("invalid-version")


def test_invalid_semantic_version_with_missing_patch() -> None:
    with pytest.raises(ValueError):
        SemanticVersion.parse("2.6")


def test_invalid_semantic_version_with_empty_value() -> None:
    with pytest.raises(ValueError):
        SemanticVersion.parse("")


# ---------------------------------------------------------------------------
# CitationVerifier tests
# ---------------------------------------------------------------------------


def test_has_citations_with_source_marker() -> None:
    verifier = CitationVerifier()

    answer = "The issue was fixed. [source: issue-123]"

    assert verifier.has_citations(answer) is True


def test_has_citations_with_github_url() -> None:
    verifier = CitationVerifier()

    answer = (
        "The fix is documented at "
        "https://github.com/pydantic/pydantic/issues/123"
    )

    assert verifier.has_citations(answer) is True


def test_has_citations_without_citation() -> None:
    verifier = CitationVerifier()

    answer = "The issue appears to be fixed."

    assert verifier.has_citations(answer) is False


def test_has_citations_with_non_string_input() -> None:
    verifier = CitationVerifier()

    assert verifier.has_citations(None) is False
    assert verifier.has_citations(123) is False


def test_valid_url() -> None:
    verifier = CitationVerifier()

    assert (
        verifier.validate_url(
            "https://github.com/pydantic/pydantic/issues/123"
        )
        is True
    )


def test_invalid_url() -> None:
    verifier = CitationVerifier()

    assert verifier.validate_url("not-a-valid-url") is False


def test_invalid_url_with_missing_scheme() -> None:
    verifier = CitationVerifier()

    assert verifier.validate_url("github.com/example/repo") is False


def test_invalid_url_with_unsupported_scheme() -> None:
    verifier = CitationVerifier()

    assert verifier.validate_url("ftp://github.com/example/repo") is False


def test_valid_citation() -> None:
    verifier = CitationVerifier()

    citation = {
        "source": "https://github.com/pydantic/pydantic/issues/123",
        "source_type": "issue",
        "record_id": "issue-123",
    }

    assert verifier.validate_citation(citation) is True


def test_invalid_citation_with_wrong_keys() -> None:
    verifier = CitationVerifier()

    citation = {
        "type": "issue",
        "url": "https://github.com/pydantic/pydantic/issues/123",
    }

    assert verifier.validate_citation(citation) is False


def test_invalid_citation_with_invalid_source() -> None:
    verifier = CitationVerifier()

    citation = {
        "source": "not-a-valid-url",
        "source_type": "issue",
        "record_id": "issue-123",
    }

    assert verifier.validate_citation(citation) is False


def test_invalid_citation_without_source() -> None:
    verifier = CitationVerifier()

    citation = {
        "source_type": "issue",
        "record_id": "issue-123",
    }

    assert verifier.validate_citation(citation) is False


def test_invalid_citation_with_empty_required_value() -> None:
    verifier = CitationVerifier()

    citation = {
        "source": "https://github.com/pydantic/pydantic/issues/123",
        "source_type": "",
        "record_id": "issue-123",
    }

    assert verifier.validate_citation(citation) is False


def test_validate_citations() -> None:
    verifier = CitationVerifier()

    citations = [
        {
            "source": "https://github.com/pydantic/pydantic/issues/123",
            "source_type": "issue",
            "record_id": "issue-123",
        },
        {
            "source": "https://github.com/pydantic/pydantic/pull/999",
            "source_type": "pull_request",
            "record_id": "pr-999",
        },
        {
            "source": "https://github.com/pydantic/pydantic/commit/ABC123",
            "source_type": "commit",
            "record_id": "commit-ABC123",
        },
    ]

    assert verifier.validate_citations(citations) is True


def test_validate_citations_with_invalid_item() -> None:
    verifier = CitationVerifier()

    citations = [
        {
            "source": "https://github.com/pydantic/pydantic/issues/123",
            "source_type": "issue",
            "record_id": "issue-123",
        },
        {
            "source": "invalid-url",
            "source_type": "pull_request",
            "record_id": "pr-999",
        },
    ]

    assert verifier.validate_citations(citations) is False


def test_validate_citations_with_empty_list() -> None:
    verifier = CitationVerifier()

    assert verifier.validate_citations([]) is False


def test_verify_evidence_block() -> None:
    verifier = CitationVerifier()

    evidence = {
        "citations": [
            {
                "source": "https://github.com/pydantic/pydantic/issues/123",
                "source_type": "issue",
                "record_id": "issue-123",
            },
            {
                "source": "https://github.com/pydantic/pydantic/pull/999",
                "source_type": "pull_request",
                "record_id": "pr-999",
            },
            {
                "source": "https://github.com/pydantic/pydantic/commit/ABC123",
                "source_type": "commit",
                "record_id": "commit-ABC123",
            },
        ]
    }

    result = verifier.verify_evidence_block(evidence)

    assert result["valid"] is True
    assert result["citation_count"] == 3
    assert result["reason"] == "Evidence citations are valid."


def test_missing_evidence_block() -> None:
    verifier = CitationVerifier()

    result = verifier.verify_evidence_block(None)

    assert result["valid"] is False
    assert result["reason"] == "Evidence block is missing or invalid."


def test_empty_evidence_block() -> None:
    verifier = CitationVerifier()

    result = verifier.verify_evidence_block({})

    assert result["valid"] is False
    assert result["reason"] == "Evidence contains no valid citations."


def test_evidence_block_with_invalid_citations() -> None:
    verifier = CitationVerifier()

    evidence = {
        "citations": [
            {
                "source": "https://github.com/pydantic/pydantic/issues/123",
                "source_type": "issue",
                "record_id": "issue-123",
            },
            {
                "source": "invalid-url",
                "source_type": "commit",
                "record_id": "commit-ABC123",
            },
        ]
    }

    result = verifier.verify_evidence_block(evidence)

    assert result["valid"] is False
    assert result["reason"] == "Evidence contains no valid citations."


def test_evidence_block_without_citations_key() -> None:
    verifier = CitationVerifier()

    result = verifier.verify_evidence_block(
        {
            "some_other_field": "value",
        }
    )

    assert result["valid"] is False
    assert result["reason"] == "Evidence contains no valid citations."
"""Stage 6 integration tests for the real-tool registry seam."""

from __future__ import annotations

from src.pipeline.tool_registry import FixLensToolRegistry, build_tool_registry


class FakeMetadataLookup:
    def get_by_issue_number(self, issue_number):
        return {"issue": {"number": issue_number}}

    def get_by_pr_number(self, pr_number):
        return {"pull_request": {"number": pr_number}}

    def get_by_commit_sha(self, commit_sha):
        return {"commit": {"sha": commit_sha}}

    def get_by_release_tag(self, release_tag):
        return {"release": {"tag_name": release_tag}}


class FakeEmbedder:
    """Fake the Stage 4 query embedder."""

    def embed_query(self, query):
        return [query]


class FakeRetriever:
    """Fake the Stage 4 retriever contract.

    Real IssueRetriever/ReleaseRetriever expect an embedded
    query vector, not the raw query string.
    """

    def retrieve(self, query_vector, **kwargs):
        return {
            "query_vector": query_vector,
            "kwargs": kwargs,
        }


class FakeVersionVerifier:
    def is_at_least(self, actual_version, required_version):
        return {
            "actual_version": actual_version,
            "required_version": required_version,
            "valid": True,
        }


class FakeCitationVerifier:
    def verify_evidence_block(self, evidence):
        return {"valid": True, "evidence": evidence}


def test_registry_builds_router_with_stage4_adapters():
    registry = build_tool_registry(
        metadata_lookup=FakeMetadataLookup(),
        issue_retriever=FakeRetriever(),
        release_retriever=FakeRetriever(),
        version_verifier=FakeVersionVerifier(),
        citation_verifier=FakeCitationVerifier(),
        embedder=FakeEmbedder(),
    )

    assert registry.is_complete()
    assert registry.missing_actions() == []

    router = registry.build_router()

    issue = router.execute("lookup_issue", {"issue_number": 11151})
    pr = router.execute("lookup_pr", {"pr_number": 3552})
    commit = router.execute("lookup_commit", {"commit_sha": "abc123"})
    release = router.execute("lookup_release", {"release_tag": "v2.0.0"})
    retrieved = router.execute(
        "retrieve_issue",
        {"query": "database validation"},
    )
    version = router.execute(
        "verify_version",
        {
            "actual_version": "2.0.0",
            "required_version": "1.0.0",
        },
    )

    assert issue["success"] is True
    assert issue["result"]["issue"]["number"] == 11151
    assert pr["result"]["pull_request"]["number"] == 3552
    assert commit["result"]["commit"]["sha"] == "abc123"
    assert release["result"]["release"]["tag_name"] == "v2.0.0"

    # The raw query is embedded before reaching the retriever.
    assert retrieved["result"]["query_vector"] == ["database validation"]

    assert version["result"]["valid"] is True


def test_registry_reports_missing_tools():
    registry = FixLensToolRegistry()
    registry.register(
        "lookup_issue",
        lambda issue_number: {"issue": {"number": issue_number}},
    )

    assert registry.is_complete() is False
    assert "lookup_pr" in registry.missing_actions()
    assert "verify_version" in registry.missing_actions()

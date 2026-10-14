"""Unit tests for deterministic FixLens verification."""

from __future__ import annotations

from src.verification.verifier import VerificationEngine


def observation(action, result, success=True):
    return {
        "action": action,
        "parameters": {},
        "success": success,
        "result": result,
    }


def test_verified_merged_pr_with_commit_is_fixed():
    evidence = [
        observation(
            "lookup_issue",
            {
                "issue": {
                    "number": 11151,
                    "title": "Example",
                    "url": "https://github.com/example/repo/issues/11151",
                }
            },
        ),
        observation(
            "lookup_pr",
            {
                "pull_request": {
                    "number": 3552,
                    "state": "closed",
                    "url": "https://github.com/example/repo/pull/3552",
                    "body": "Fixes #11151",
                    "merged_at": "2021-12-24T13:11:06Z",
                    "merge_commit_sha": "abc123",
                }
            },
        ),
    ]

    result = VerificationEngine().verify({}, evidence)

    assert result.status == "FIXED"
    assert result.issue_verified is True
    assert result.pr_verified is True
    assert result.issue_pr_relation_verified is True
    assert result.pr_merged is True
    assert result.commit_verified is True
    assert result.release_verified is False


def test_missing_release_is_not_treated_as_not_released():
    evidence = [
        observation(
            "lookup_pr",
            {
                "pull_request": {
                    "number": 10,
                    "url": "https://github.com/example/repo/pull/10",
                    "body": "Fixes #123",
                    "merged_at": "2025-01-01T00:00:00Z",
                    "merge_commit_sha": "abc123",
                }
            },
        ),
        observation(
            "lookup_issue",
            {
                "issue": {
                    "number": 123,
                    "url": "https://github.com/example/repo/issues/123",
                }
            },
        ),
        observation(
            "lookup_release",
            {
                "version_info": {
                    "release": None,
                    "tag_name": None,
                }
            },
        ),
    ]

    result = VerificationEngine().verify({}, evidence)

    assert result.status == "FIXED"
    assert result.release_verified is False
    assert "release evidence" in result.reason.lower()


def test_unmerged_pr_is_not_fixed():
    evidence = [
        observation(
            "lookup_issue",
            {"issue": {"number": 20}},
        ),
        observation(
            "lookup_pr",
            {
                "pull_request": {
                    "number": 30,
                    "url": "https://github.com/example/repo/pull/30",
                    "body": "Fixes #20",
                    "state": "closed",
                    "merged_at": None,
                    "merge_commit_sha": None,
                }
            },
        ),
        observation(
            "lookup_issue",
            {
                "issue": {
                    "number": 20,
                    "url": "https://github.com/example/repo/issues/20",
                }
            },
        ),
    ]

    result = VerificationEngine().verify({}, evidence)

    assert result.status == "NOT_VERIFIED"
    assert result.pr_verified is True
    assert result.pr_merged is False
    assert result.commit_verified is False


def test_no_issue_evidence_returns_insufficient_evidence():
    result = VerificationEngine().verify({}, [])

    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.issue_verified is False
    assert result.pr_verified is False


def test_release_is_verified_when_commit_matches():
    evidence = [
        observation(
            "lookup_issue",
            {
                "issue": {
                    "number": 20,
                    "url": "https://github.com/example/repo/issues/20",
                }
            },
        ),
        observation(
            "lookup_pr",
            {
                "pull_request": {
                    "number": 30,
                    "url": "https://github.com/example/repo/pull/30",
                    "body": "Fixes #20",
                    "merged_at": "2025-01-01T00:00:00Z",
                    "merge_commit_sha": "abc123",
                }
            },
        ),
        observation(
            "lookup_release",
            {
                "release": {
                    "tag_name": "v2.0.0",
                    "merge_commit_sha": "abc123",
                }
            },
        ),
    ]

    result = VerificationEngine().verify({}, evidence)

    assert result.status == "FIXED"
    assert result.release_verified is True


def test_cross_repository_reference_does_not_prove_issue_fix():
    evidence = [
        observation(
            "lookup_issue",
            {
                "issue": {
                    "number": 11151,
                    "state": "open",
                    "url": "https://api.github.com/repos/pydantic/pydantic/issues/11151",
                }
            },
        ),
        observation(
            "lookup_pr",
            {
                "pull_request": {
                    "number": 3552,
                    "title": "build(deps): bump mypy from 0.910 to 0.920",
                    "body": (
                        'Bumps mypy; includes '
                        '<a href="https://github-redirect.com/python/mypy/issues/11151">'
                        "#11151</a>."
                    ),
                    "url": "https://github.com/pydantic/pydantic/pull/3552",
                    "merged_at": "2021-12-24T13:11:06Z",
                    "merge_commit_sha": "e14e7561ede74c6cb159d2e063085a0184767e37",
                }
            },
        ),
    ]

    result = VerificationEngine().verify({}, evidence)

    assert result.status == "NOT_VERIFIED"
    assert result.pr_verified is True
    assert result.pr_merged is True
    assert result.commit_verified is True
    assert result.issue_pr_relation_verified is False
    assert "does not establish" in result.reason

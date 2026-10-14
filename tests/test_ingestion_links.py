"""Regression tests for repository-aware issue-to-PR link extraction."""

from __future__ import annotations

import json

from src.ingestion import build_metadata
from src.ingestion.resolve_links import extract_issue_numbers, resolve_link_records
from src.ingestion.resolve_versions import resolve_release_mappings

PYDANTIC = ("pydantic", "pydantic")


def test_extract_issue_numbers_ignores_other_repository_references():
    text = (
        'See <a href="https://github-redirect.dependabot.com/python/mypy/'
        'issues/11151">#11151</a>, python/mypy#11151, '
        "and https://github.com/python/mypy/issues/11151. "
        "Fixes #2142 and https://github.com/pydantic/pydantic/issues/13."
    )

    assert extract_issue_numbers(text, PYDANTIC) == {13, 2142}


def test_extract_issue_numbers_accepts_same_repository_qualified_links():
    text = "Fixes pydantic/pydantic#2142 and closes #2143."

    assert extract_issue_numbers(text, PYDANTIC) == {2142, 2143}


def test_link_resolver_does_not_join_cross_repository_number_collision():
    issues = [
        {
            "number": 11151,
            "html_url": "https://github.com/pydantic/pydantic/issues/11151",
        },
        {
            "number": 11151,
            "html_url": "https://github.com/python/mypy/issues/11151",
        },
    ]
    prs = [{
        "number": 3552,
        "html_url": "https://github.com/pydantic/pydantic/pull/3552",
        "title": "Bump mypy",
        "body": (
            '<a href="https://github-redirect.dependabot.com/python/mypy/'
            'issues/11151">#11151</a>'
        ),
    }]

    assert resolve_link_records(issues, prs) == []


def test_link_resolver_keeps_same_repository_closing_reference():
    issues = [{
        "number": 2142,
        "html_url": "https://github.com/pydantic/pydantic/issues/2142",
    }]
    prs = [{
        "number": 2143,
        "html_url": "https://github.com/pydantic/pydantic/pull/2143",
        "title": "Fix required optional default",
        "body": "closes #2142",
        "state": "closed",
        "merged_at": "2020-11-30T17:55:51Z",
    }]

    mappings = resolve_link_records(issues, prs)
    assert len(mappings) == 1
    assert mappings[0]["issue_number"] == 2142
    assert mappings[0]["pr_number"] == 2143
    assert mappings[0]["repository"] == "pydantic/pydantic"


def test_release_links_are_scoped_by_repository():
    mappings = [
        {
            "repository": "pydantic/pydantic",
            "pr_number": 2143,
            "pr_url": "https://github.com/pydantic/pydantic/pull/2143",
        },
        {
            "repository": "another/project",
            "pr_number": 2143,
            "pr_url": "https://github.com/another/project/pull/2143",
        },
        {
            "repository": "pydantic/pydantic",
            "pr_number": 3552,
            "pr_url": "https://github.com/pydantic/pydantic/pull/3552",
        },
    ]
    releases = [{
        "html_url": "https://github.com/pydantic/pydantic/releases/tag/v1.8",
        "tag_name": "v1.8",
        "body": "Fixes #2143; unrelated python/mypy#3552",
    }]

    resolved = resolve_release_mappings(mappings, releases)

    assert resolved[0]["version_info"]["tag_name"] == "v1.8"
    assert resolved[1]["version_info"]["tag_name"] is None
    assert resolved[2]["version_info"]["tag_name"] is None


def test_metadata_builder_does_not_join_same_number_across_repositories(
    tmp_path, monkeypatch
):
    issues = [
        {
            "number": 11151,
            "title": "Pydantic issue",
            "html_url": "https://github.com/pydantic/pydantic/issues/11151",
        },
        {
            "number": 11151,
            "title": "Mypy issue",
            "html_url": "https://github.com/python/mypy/issues/11151",
        },
    ]
    prs = [
        {
            "number": 3552,
            "html_url": "https://github.com/pydantic/pydantic/pull/3552",
        },
        {
            "number": 3552,
            "html_url": "https://github.com/python/mypy/pull/3552",
        },
    ]
    mapping = {
        "repository": "pydantic/pydantic",
        "issue_number": 11151,
        "pr_number": 3552,
        "pr_url": "https://github.com/pydantic/pydantic/pull/3552",
    }
    output_path = tmp_path / "metadata.json"
    monkeypatch.setattr(build_metadata, "load_json_pages", lambda path: (
        issues if path == build_metadata.ISSUES_DIR else prs
    ))
    monkeypatch.setattr(build_metadata, "load_version_mappings", lambda: [mapping])
    monkeypatch.setattr(build_metadata, "load_comments", lambda issue_number: [])
    monkeypatch.setattr(build_metadata, "OUTPUT_PATH", output_path)

    assert build_metadata.build_metadata() == 1
    record = json.loads(output_path.read_text(encoding="utf-8"))[0]
    assert record["repository"] == "pydantic/pydantic"
    assert record["issue"]["title"] == "Pydantic issue"
    assert record["pull_request"]["url"] == mapping["pr_url"]

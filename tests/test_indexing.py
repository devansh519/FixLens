import json

from src.indexing.cleaners import (
    build_issue_document,
    build_pr_document,
    build_release_document,
    clean_text,
)
from src.indexing.chunker import split_text


def test_clean_text_removes_extra_whitespace() -> None:
    text = "Hello   world\n\n\nTest"
    result = clean_text(text)

    assert result == "Hello world\n\nTest"


def test_build_issue_document() -> None:
    issue = {
        "number": 123,
        "title": "Example issue",
        "state": "open",
        "body": "Example problem",
        "comments": [],
    }

    document = build_issue_document(issue)

    assert "Issue #123" in document
    assert "Example issue" in document
    assert "Example problem" in document


def test_build_pr_document() -> None:
    pr = {
        "number": 456,
        "title": "Fix example issue",
        "state": "closed",
        "body": "This fixes the problem",
        "merged": True,
        "merge_commit_sha": "abc123",
    }

    document = build_pr_document(pr)

    assert "Pull Request #456" in document
    assert "Fix example issue" in document
    assert "abc123" in document


def test_build_release_document() -> None:
    release = {
        "tag_name": "v1.2.0",
        "name": "Version 1.2.0",
        "body": "Bug fixes",
        "published_at": "2025-01-01T00:00:00Z",
        "target_commitish": "main",
    }

    document = build_release_document(release)

    assert "v1.2.0" in document
    assert "Bug fixes" in document


def test_split_text_creates_chunks() -> None:
    text = " ".join(["word"] * 100)

    chunks = split_text(
        text,
        chunk_size=20,
        chunk_overlap=5,
    )

    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)


def test_split_text_preserves_overlap() -> None:
    words = [f"word{i}" for i in range(30)]
    text = " ".join(words)

    chunks = split_text(
        text,
        chunk_size=10,
        chunk_overlap=3,
    )

    first_words = chunks[0].split()
    second_words = chunks[1].split()

    assert first_words[-3:] == second_words[:3]
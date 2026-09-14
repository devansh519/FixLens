import json
from pathlib import Path


EMBEDDED_PATH = Path("data/processed/embedded_chunks.jsonl")
ISSUE_PR_INDEX_PATH = Path("data/processed/issue_pr_index.jsonl")
RELEASE_INDEX_PATH = Path("data/processed/release_index.jsonl")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def test_embedded_chunks_exist() -> None:
    records = read_jsonl(EMBEDDED_PATH)

    assert records, "No embedded chunks found"

    record = records[0]

    assert "chunk_id" in record
    assert "text" in record
    assert "embedding" in record
    assert isinstance(record["embedding"], list)
    assert len(record["embedding"]) > 0


def test_issue_pr_index_structure() -> None:
    records = read_jsonl(ISSUE_PR_INDEX_PATH)

    assert records, "Issue/PR index is empty"

    record = records[0]

    assert "id" in record
    assert "vector" in record
    assert "text" in record
    assert "metadata" in record

    assert isinstance(record["vector"], list)
    assert len(record["vector"]) > 0


def test_issue_pr_index_contains_only_issue_or_pr_records() -> None:
    records = read_jsonl(ISSUE_PR_INDEX_PATH)

    assert records

    source_types = {
        record["metadata"].get("source_type")
        for record in records
    }

    assert source_types.issubset({"issue", "pull_request"})


def test_release_index_structure() -> None:
    records = read_jsonl(RELEASE_INDEX_PATH)

    # This test is skipped if no release chunks were generated.
    if not records:
        return

    record = records[0]

    assert "id" in record
    assert "vector" in record
    assert "text" in record
    assert "metadata" in record

    assert isinstance(record["vector"], list)
    assert len(record["vector"]) > 0


def test_index_vectors_have_consistent_dimensions() -> None:
    issue_pr_records = read_jsonl(ISSUE_PR_INDEX_PATH)
    release_records = read_jsonl(RELEASE_INDEX_PATH)

    records = issue_pr_records + release_records

    assert records

    dimensions = {
        len(record["vector"])
        for record in records
    }

    assert len(dimensions) == 1
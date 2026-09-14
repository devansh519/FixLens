
import json
from pathlib import Path
from typing import Any

from src.indexing.cleaners import (
    build_issue_document,
    build_pr_document,
    build_release_document,
    clean_record,
)


INPUT_PATH = Path("storage/metadata/issue_pr_version.json")
OUTPUT_PATH = Path("data/processed/chunks.jsonl")


def load_metadata() -> list[dict[str, Any]]:
    """Load the combined metadata file."""
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing metadata file: {INPUT_PATH}")

    with INPUT_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Metadata file must contain a list of records")

    return data


def split_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[str]:
    """Split text into overlapping word-based chunks."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be >= 0 and smaller than chunk_size"
        )

    words = text.split()

    if not words:
        return []

    chunks = []
    start = 0
    step = chunk_size - chunk_overlap

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end]).strip()

        if chunk:
            chunks.append(chunk)

        if end == len(words):
            break

        start += step

    return chunks


def create_record_chunks(
    record: dict[str, Any],
    record_id: int,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[dict[str, Any]]:
    """Create searchable chunks from one metadata record."""
    cleaned_record = clean_record(record)

    issue = cleaned_record.get("issue", {})
    pull_request = cleaned_record.get("pull_request", {})
    version_info = cleaned_record.get("version_info", {})
    evidence = cleaned_record.get("evidence", {})

    documents = [
        (
            "issue",
            build_issue_document(issue),
        ),
        (
            "pull_request",
            build_pr_document(pull_request),
        ),
    ]

    release = version_info.get("release")

    if release:
        documents.append(
            (
                "release",
                build_release_document(release),
            )
        )

    chunks = []

    for source_type, document in documents:
        text_chunks = split_text(
            document,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        for chunk_index, text in enumerate(text_chunks):
            chunks.append(
                {
                    "chunk_id": (
                        f"record_{record_id}_"
                        f"{source_type}_{chunk_index}"
                    ),
                    "record_id": record_id,
                    "source_type": source_type,
                    "chunk_index": chunk_index,
                    "text": text,
                    "metadata": {
                        "issue_number": issue.get("number"),
                        "pr_number": pull_request.get("number"),
                        "issue_url": evidence.get("issue_url"),
                        "pr_url": evidence.get("pr_url"),
                        "merge_commit_sha": evidence.get(
                            "merge_commit_sha"
                        ),
                        "tag_name": version_info.get("tag_name"),
                        "release_tag": (
                            release.get("tag_name")
                            if release
                            else None
                        ),
                    },
                }
            )

    return chunks


def build_chunks() -> int:
    """Build chunks for all metadata records."""
    records = load_metadata()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    total_chunks = 0

    with OUTPUT_PATH.open("w", encoding="utf-8") as output_file:
        for record_id, record in enumerate(records):
            record_chunks = create_record_chunks(
                record=record,
                record_id=record_id,
            )

            for chunk in record_chunks:
                output_file.write(
                    json.dumps(chunk, ensure_ascii=False) + "\n"
                )

            total_chunks += len(record_chunks)

    print(f"[SAVED] {OUTPUT_PATH}")
    print(f"Metadata records processed: {len(records)}")
    print(f"Total chunks created: {total_chunks}")

    return total_chunks


def main() -> None:
    build_chunks()


if __name__ == "__main__":
    main()
    

import json
from pathlib import Path
from typing import Any


INPUT_PATH = Path("data/processed/embedded_chunks.jsonl")
OUTPUT_PATH = Path("data/processed/issue_pr_index.jsonl")


def load_embedded_chunks() -> list[dict[str, Any]]:
    """Load embedded chunks from JSONL."""
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing embeddings file: {INPUT_PATH}")

    chunks = []

    with INPUT_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                chunks.append(json.loads(line))

    return chunks


def build_issue_pr_index() -> int:
    """Create an index containing only issue and pull-request chunks."""
    chunks = load_embedded_chunks()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    selected_count = 0

    with OUTPUT_PATH.open("w", encoding="utf-8") as output_file:
        for chunk in chunks:
            source_type = chunk.get("source_type")

            if source_type not in {"issue", "pull_request"}:
                continue

            index_record = {
                "id": chunk.get("chunk_id"),
                "vector": chunk.get("embedding"),
                "text": chunk.get("text"),
                "metadata": {
                    **chunk.get("metadata", {}),
                    "source_type": source_type,
                    "record_id": chunk.get("record_id"),
                    "chunk_index": chunk.get("chunk_index"),
                },
            }

            output_file.write(
                json.dumps(index_record, ensure_ascii=False) + "\n"
            )

            selected_count += 1

    print(f"[SAVED] {OUTPUT_PATH}")
    print(f"Issue/PR vectors indexed: {selected_count}")

    return selected_count


def main() -> None:
    build_issue_pr_index()


if __name__ == "__main__":
    main()

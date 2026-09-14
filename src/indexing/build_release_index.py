import json
from pathlib import Path


EMBEDDED_PATH = Path("data/processed/embedded_chunks.jsonl")
OUTPUT_PATH = Path("data/processed/release_index.jsonl")


def build_release_index() -> None:
    if not EMBEDDED_PATH.exists():
        raise FileNotFoundError(f"Missing file: {EMBEDDED_PATH}")

    release_records = []

    with EMBEDDED_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            chunk = json.loads(line)

            if chunk.get("source_type") != "release":
                continue

            record = {
                "id": chunk["chunk_id"],
                "vector": chunk["embedding"],
                "text": chunk["text"],
                "metadata": {
                    **chunk.get("metadata", {}),
                    "source_type": "release",
                    "record_id": chunk.get("record_id"),
                    "chunk_index": chunk.get("chunk_index", 0),
                },
            }

            release_records.append(record)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        for record in release_records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"[SAVED] {OUTPUT_PATH}")
    print(f"Release chunks indexed: {len(release_records)}")


if __name__ == "__main__":
    build_release_index()
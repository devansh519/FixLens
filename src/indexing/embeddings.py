
import json
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer


INPUT_PATH = Path("data/processed/chunks.jsonl")
OUTPUT_PATH = Path("data/processed/embedded_chunks.jsonl")

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_chunks() -> list[dict[str, Any]]:
    """Load text chunks from JSONL."""
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing chunks file: {INPUT_PATH}")

    chunks = []

    with INPUT_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                chunks.append(json.loads(line))

    return chunks


def generate_embeddings(
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate embeddings for every text chunk."""
    if not chunks:
        return []

    print(f"Loading embedding model: {MODEL_NAME}")

    model = SentenceTransformer(MODEL_NAME)

    texts = [chunk["text"] for chunk in chunks]

    print(f"Generating embeddings for {len(texts)} chunks...")

    vectors = model.encode(
        texts,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    embedded_chunks = []

    for chunk, vector in zip(chunks, vectors):
        embedded_chunk = {
            **chunk,
            "embedding": vector.tolist(),
        }

        embedded_chunks.append(embedded_chunk)

    return embedded_chunks


def save_embeddings(
    embedded_chunks: list[dict[str, Any]],
) -> None:
    """Save chunks and their embeddings to JSONL."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        for chunk in embedded_chunks:
            file.write(
                json.dumps(chunk, ensure_ascii=False) + "\n"
            )

    print(f"[SAVED] {OUTPUT_PATH}")
    print(f"Embedded chunks: {len(embedded_chunks)}")


def main() -> None:
    chunks = load_chunks()
    embedded_chunks = generate_embeddings(chunks)
    save_embeddings(embedded_chunks)


if __name__ == "__main__":
    main()
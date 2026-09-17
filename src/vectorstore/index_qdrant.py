from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from qdrant_client.http import models

from src.vectorstore.qdrant_client import FixLensQdrantClient


EMBEDDED_CHUNKS_PATH = Path(
    "data/processed/embedded_chunks.jsonl"
)

BATCH_SIZE = 64


def load_embedded_chunks(
    path: Path = EMBEDDED_CHUNKS_PATH,
) -> list[dict[str, Any]]:
    """Load embedded chunks from a JSONL file."""
    if not path.exists():
        raise FileNotFoundError(
            f"Embedding file not found: {path}"
        )

    chunks: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON at line {line_number}"
                ) from error

            if "embedding" not in chunk:
                raise ValueError(
                    f"Missing embedding at line {line_number}"
                )

            if "chunk_id" not in chunk:
                raise ValueError(
                    f"Missing chunk_id at line {line_number}"
                )

            chunks.append(chunk)

    return chunks


def get_collection_name(
    source_type: str,
) -> str | None:
    """Map a chunk source type to a Qdrant collection."""
    if source_type in {"issue", "pull_request"}:
        return FixLensQdrantClient.ISSUES_PRS_COLLECTION

    if source_type == "release":
        return FixLensQdrantClient.RELEASES_COLLECTION

    return None


def build_payload(chunk: dict[str, Any]) -> dict[str, Any]:
    """Build the searchable payload stored with each vector."""
    return {
        "chunk_id": chunk.get("chunk_id"),
        "record_id": chunk.get("record_id"),
        "source_type": chunk.get("source_type"),
        "chunk_index": chunk.get("chunk_index"),
        "text": chunk.get("text", ""),
        "metadata": chunk.get("metadata", {}),
    }


def build_point(
    chunk: dict[str, Any],
    point_id: int,
) -> models.PointStruct:
    """Convert one embedded chunk into a Qdrant point."""
    embedding = chunk["embedding"]

    return models.PointStruct(
        id=point_id,
        vector=embedding,
        payload=build_payload(chunk),
    )


def upload_chunks(
    client: FixLensQdrantClient,
    chunks: list[dict[str, Any]],
) -> dict[str, int]:
    """Create collections and upload chunks in batches."""
    if not chunks:
        return {}

    vector_size = len(chunks[0]["embedding"])

    for chunk in chunks:
        if len(chunk["embedding"]) != vector_size:
            raise ValueError(
                "All embeddings must have the same vector dimension."
            )

    client.ensure_default_collections(vector_size)

    grouped_chunks: dict[str, list[dict[str, Any]]] = {
        FixLensQdrantClient.ISSUES_PRS_COLLECTION: [],
        FixLensQdrantClient.RELEASES_COLLECTION: [],
    }

    for chunk in chunks:
        collection_name = get_collection_name(
            chunk.get("source_type", "")
        )

        if collection_name is None:
            continue

        grouped_chunks[collection_name].append(chunk)

    counts: dict[str, int] = {}

    for collection_name, collection_chunks in grouped_chunks.items():
        points: list[models.PointStruct] = []

        for point_id, chunk in enumerate(collection_chunks):
            points.append(
                build_point(
                    chunk=chunk,
                    point_id=point_id,
                )
            )

            if len(points) >= BATCH_SIZE:
                client.upsert_points(
                    collection_name=collection_name,
                    points=points,
                )
                points.clear()

        if points:
            client.upsert_points(
                collection_name=collection_name,
                points=points,
            )

        counts[collection_name] = len(collection_chunks)

    return counts


def main() -> None:
    """Load local embeddings and upload them to Qdrant."""
    print("Loading embedded chunks...")
    chunks = load_embedded_chunks()

    print(f"Loaded {len(chunks)} chunks.")

    client = FixLensQdrantClient()

    if not client.health_check():
        raise RuntimeError(
            "Qdrant is not reachable. "
            "Start it using: docker compose up -d"
        )

    print("Qdrant connection successful.")

    counts = upload_chunks(
        client=client,
        chunks=chunks,
    )

    print("\nUpload completed:")

    for collection_name, count in counts.items():
        print(f"- {collection_name}: {count} vectors")

    print("\nStored vector counts:")

    for collection_name in counts:
        stored_count = client.count(collection_name)
        print(f"- {collection_name}: {stored_count}")


if __name__ == "__main__":
    main()
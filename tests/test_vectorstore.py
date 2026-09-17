from __future__ import annotations

import json
from pathlib import Path

import pytest
from qdrant_client.http import models

from src.vectorstore.index_qdrant import (
    build_payload,
    build_point,
    get_collection_name,
    load_embedded_chunks,
)
from src.vectorstore.qdrant_client import FixLensQdrantClient


VECTOR_SIZE = 384


def make_chunk(
    source_type: str = "issue",
    chunk_id: str = "record_0_issue_0",
) -> dict:
    """Create a minimal embedded chunk for testing."""
    return {
        "chunk_id": chunk_id,
        "record_id": 0,
        "source_type": source_type,
        "chunk_index": 0,
        "text": "Example FixLens issue text.",
        "metadata": {
            "issue_number": 123,
            "pr_number": 456,
        },
        "embedding": [0.1] * VECTOR_SIZE,
    }


def test_load_embedded_chunks(tmp_path: Path) -> None:
    """Embedded chunks should be loaded from JSONL."""
    file_path = tmp_path / "embedded_chunks.jsonl"

    chunks = [
        make_chunk(),
        make_chunk(
            source_type="release",
            chunk_id="record_1_release_0",
        ),
    ]

    with file_path.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(chunk) + "\n")

    result = load_embedded_chunks(file_path)

    assert len(result) == 2
    assert result[0]["chunk_id"] == "record_0_issue_0"
    assert result[1]["source_type"] == "release"


def test_load_embedded_chunks_missing_file(tmp_path: Path) -> None:
    """A missing embedding file should raise FileNotFoundError."""
    file_path = tmp_path / "missing.jsonl"

    with pytest.raises(FileNotFoundError):
        load_embedded_chunks(file_path)


def test_load_embedded_chunks_missing_embedding(
    tmp_path: Path,
) -> None:
    """Chunks without embeddings should be rejected."""
    file_path = tmp_path / "invalid.jsonl"

    invalid_chunk = make_chunk()
    invalid_chunk.pop("embedding")

    file_path.write_text(
        json.dumps(invalid_chunk) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Missing embedding"):
        load_embedded_chunks(file_path)


def test_collection_mapping() -> None:
    """Source types should map to the correct collections."""
    assert (
        get_collection_name("issue")
        == FixLensQdrantClient.ISSUES_PRS_COLLECTION
    )

    assert (
        get_collection_name("pull_request")
        == FixLensQdrantClient.ISSUES_PRS_COLLECTION
    )

    assert (
        get_collection_name("release")
        == FixLensQdrantClient.RELEASES_COLLECTION
    )

    assert get_collection_name("unknown") is None


def test_build_payload() -> None:
    """Payload should preserve searchable chunk information."""
    chunk = make_chunk()

    payload = build_payload(chunk)

    assert payload["chunk_id"] == chunk["chunk_id"]
    assert payload["record_id"] == chunk["record_id"]
    assert payload["source_type"] == chunk["source_type"]
    assert payload["chunk_index"] == chunk["chunk_index"]
    assert payload["text"] == chunk["text"]
    assert payload["metadata"] == chunk["metadata"]


def test_build_point() -> None:
    """An embedded chunk should become a valid Qdrant point."""
    chunk = make_chunk()

    point = build_point(chunk, point_id=10)

    assert isinstance(point, models.PointStruct)
    assert point.id == 10
    assert len(point.vector) == VECTOR_SIZE
    assert point.payload["chunk_id"] == chunk["chunk_id"]


def test_qdrant_client_initialization() -> None:
    """The Qdrant wrapper should initialize with local defaults."""
    client = FixLensQdrantClient()

    try:
        assert client.host == "localhost"
        assert client.port == 6333
        assert client.client is not None
    finally:
        client.close()


@pytest.mark.integration
def test_qdrant_health_check() -> None:
    """Qdrant should be reachable when the Docker container is running."""
    client = FixLensQdrantClient()

    try:
        assert client.health_check() is True
    finally:
        client.close()


@pytest.mark.integration
def test_qdrant_collections_exist() -> None:
    """The uploaded FixLens collections should exist in Qdrant."""
    client = FixLensQdrantClient()

    try:
        assert client.collection_exists(
            FixLensQdrantClient.ISSUES_PRS_COLLECTION
        )

        assert client.collection_exists(
            FixLensQdrantClient.RELEASES_COLLECTION
        )
    finally:
        client.close()


@pytest.mark.integration
def test_qdrant_vector_counts() -> None:
    """Qdrant should contain the expected uploaded vector counts."""
    client = FixLensQdrantClient()

    try:
        assert (
            client.count(FixLensQdrantClient.ISSUES_PRS_COLLECTION)
            == 806
        )

        assert (
            client.count(FixLensQdrantClient.RELEASES_COLLECTION)
            == 54
        )
    finally:
        client.close()


@pytest.mark.integration
def test_qdrant_similarity_search() -> None:
    """Qdrant should return results for a valid query vector."""
    client = FixLensQdrantClient()

    try:
        query_vector = [0.1] * VECTOR_SIZE

        results = client.search(
            collection_name=FixLensQdrantClient.ISSUES_PRS_COLLECTION,
            query_vector=query_vector,
            limit=3,
        )

        assert len(results) > 0
        assert results[0].payload is not None
        assert "text" in results[0].payload
    finally:
        client.close()
from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models


load_dotenv()


class FixLensQdrantClient:
    """Qdrant client wrapper for FixLens vector collections."""

    ISSUES_PRS_COLLECTION = "issues_prs"
    RELEASES_COLLECTION = "releases"

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        url: str | None = None,
    ) -> None:
        self.host = host or os.getenv("QDRANT_HOST", "localhost")
        self.port = port or int(os.getenv("QDRANT_PORT", "6333"))
        self.url = url or os.getenv("QDRANT_URL")

        if self.url:
            self.client = QdrantClient(url=self.url)
        else:
            self.client = QdrantClient(
                host=self.host,
                port=self.port,
            )

    def health_check(self) -> bool:
        """Return True if Qdrant is reachable."""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False

    def collection_exists(self, collection_name: str) -> bool:
        """Check whether a collection exists."""
        collections = self.client.get_collections().collections

        return any(
            collection.name == collection_name
            for collection in collections
        )

    def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: models.Distance = models.Distance.COSINE,
    ) -> None:
        """Create a collection if it does not already exist."""
        if self.collection_exists(collection_name):
            return

        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=distance,
            ),
        )

    def ensure_default_collections(self, vector_size: int) -> None:
        """Create the standard FixLens collections."""
        self.create_collection(
            collection_name=self.ISSUES_PRS_COLLECTION,
            vector_size=vector_size,
        )

        self.create_collection(
            collection_name=self.RELEASES_COLLECTION,
            vector_size=vector_size,
        )

    def upsert_points(
        self,
        collection_name: str,
        points: list[models.PointStruct],
    ) -> None:
        """Insert or update points in a collection."""
        if not points:
            return

        self.client.upsert(
            collection_name=collection_name,
            points=points,
            wait=True,
        )

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 5,
    ) -> list[Any]:
        """Search a collection using a query embedding."""
        results = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
        )

        return results.points

    def count(self, collection_name: str) -> int:
        """Return the number of stored points."""
        result = self.client.count(
            collection_name=collection_name,
            exact=True,
        )

        return result.count

    def close(self) -> None:
        """Close the underlying Qdrant client."""
        self.client.close()
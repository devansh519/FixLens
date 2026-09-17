from __future__ import annotations

from typing import Any

from src.vectorstore.qdrant_client import FixLensQdrantClient


class ReleaseRetriever:
    """Retrieve relevant GitHub release information from Qdrant."""

    COLLECTION_NAME = "releases"

    def __init__(self, qdrant_client: FixLensQdrantClient) -> None:
        self.qdrant_client = qdrant_client

    def retrieve(
        self,
        query_vector: list[float],
        limit: int = 5,
    ) -> list[Any]:
        """
        Retrieve the most relevant releases.

        Args:
            query_vector: Embedded representation of the search query.
            limit: Maximum number of results to return.

        Returns:
            A list of Qdrant search results.
        """
        return self.qdrant_client.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=query_vector,
            limit=limit,
        )
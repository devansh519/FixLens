"""Query embedding adapter for FixLens Stage 6 retrieval."""

from __future__ import annotations

import os
from typing import Any

from sentence_transformers import SentenceTransformer


class QueryEmbedder:
    """Encode one user/retrieval query using the same model as indexing."""

    MODEL_NAME = os.getenv(
        "FIXLENS_EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )

    def __init__(self, model: Any | None = None) -> None:
        self.model = model

    def _model(self) -> Any:
        if self.model is None:
            self.model = SentenceTransformer(self.MODEL_NAME)
        return self.model

    def embed_query(self, query: str) -> list[float]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string.")
        vector = self._model().encode(
            query.strip(),
            normalize_embeddings=True,
        )
        return vector.tolist()

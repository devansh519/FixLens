"""
Real Stage 4 tool registry for FixLens.

Adapters here match the actual APIs in the current repository:
- MetadataLookup.get_by_* -> exact metadata
- IssueRetriever/ReleaseRetriever.retrieve -> Qdrant retrieval
- VersionVerifier -> deterministic semantic comparison
- CitationVerifier.verify_evidence_block -> deterministic citation check

The registry also supports dependency injection so tests can provide
fake Stage 4 components without constructing Qdrant/embedding clients.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.embeddings.embedder import QueryEmbedder
from src.pipeline.router import ToolRouter
from src.retrieval.issue_retriever import IssueRetriever
from src.retrieval.release_retriever import ReleaseRetriever
from src.tools.citation_verifier import CitationVerifier
from src.tools.metadata_lookup import MetadataLookup
from src.tools.version_verifier import VersionVerifier
from src.vectorstore.qdrant_client import FixLensQdrantClient


class FixLensToolRegistry:
    """Registry containing the deterministic tools available to FixLens."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, action: str, tool: Callable[..., Any]) -> None:
        """Register a callable under a supported FixLens action."""

        router = ToolRouter()

        if action not in router.ALLOWED_ACTIONS:
            raise ValueError(
                f"Unsupported FixLens action: {action!r}"
            )

        if not callable(tool):
            raise TypeError("tool must be callable.")

        self._tools[action] = tool

    def build_router(self) -> ToolRouter:
        """Build a ToolRouter using the currently registered tools."""
        return ToolRouter(self._tools)

    def available_actions(self) -> list[str]:
        """Return registered actions in deterministic order."""
        return sorted(self._tools)

    def missing_actions(self) -> list[str]:
        """Return supported actions that have not been registered."""
        return sorted(
            ToolRouter.ALLOWED_ACTIONS - self._tools.keys()
        )

    def is_complete(self) -> bool:
        """Return True when all supported FixLens actions are registered."""
        return not self.missing_actions()


def build_real_tool_registry(
    *,
    metadata_path: str | Path = "storage/metadata/issue_pr_version.json",
    qdrant_client: FixLensQdrantClient | None = None,
    embedder: QueryEmbedder | None = None,
    retrieval_limit: int = 5,
) -> FixLensToolRegistry:
    """
    Build the registry using the real Stage 4 components.

    This is kept as the explicit real-component factory.
    """

    return build_tool_registry(
        metadata_path=metadata_path,
        qdrant_client=qdrant_client,
        embedder=embedder,
        retrieval_limit=retrieval_limit,
    )


def build_tool_registry(
    *,
    metadata_lookup: MetadataLookup | None = None,
    issue_retriever: IssueRetriever | None = None,
    release_retriever: ReleaseRetriever | None = None,
    version_verifier: VersionVerifier | None = None,
    citation_verifier: CitationVerifier | None = None,
    metadata_path: str | Path = "storage/metadata/issue_pr_version.json",
    qdrant_client: FixLensQdrantClient | None = None,
    embedder: QueryEmbedder | None = None,
    retrieval_limit: int = 5,
) -> FixLensToolRegistry:
    """
    Build the FixLens tool registry.

    Real Stage 4 components are created automatically when dependencies
    are not supplied.

    Tests can inject fake implementations through:
    - metadata_lookup
    - issue_retriever
    - release_retriever
    - version_verifier
    - citation_verifier
    """

    # ---------------------------------------------------------
    # Stage 4 dependencies
    # ---------------------------------------------------------

    metadata = metadata_lookup or MetadataLookup(metadata_path)

    if issue_retriever is None or release_retriever is None:
        qdrant = qdrant_client or FixLensQdrantClient()

        if issue_retriever is None:
            issue_retriever = IssueRetriever(qdrant)

        if release_retriever is None:
            release_retriever = ReleaseRetriever(qdrant)

    query_embedder = embedder or QueryEmbedder()

    version_verifier = version_verifier or VersionVerifier()
    citation_verifier = citation_verifier or CitationVerifier()

    registry = FixLensToolRegistry()

    # ---------------------------------------------------------
    # Metadata lookup tools
    # ---------------------------------------------------------

    registry.register(
        "lookup_issue",
        lambda issue_number: metadata.get_by_issue_number(
            int(issue_number)
        ),
    )

    registry.register(
        "lookup_pr",
        lambda pr_number: metadata.get_by_pr_number(
            int(pr_number)
        ),
    )

    registry.register(
        "lookup_commit",
        lambda commit_sha: metadata.get_by_commit_sha(
            str(commit_sha)
        ),
    )

    registry.register(
        "lookup_release",
        lambda release_tag: metadata.get_by_release_tag(
            str(release_tag)
        ),
    )

    # ---------------------------------------------------------
    # Semantic retrieval tools
    # ---------------------------------------------------------

    def retrieve_issue(
        query: str,
        limit: int = retrieval_limit,
    ) -> list[Any]:
        """Retrieve relevant issue/PR records from Qdrant."""

        vector = query_embedder.embed_query(query)

        return issue_retriever.retrieve(
            vector,
            limit=limit,
        )

    def retrieve_release(
        query: str,
        limit: int = retrieval_limit,
    ) -> list[Any]:
        """Retrieve relevant release records from Qdrant."""

        vector = query_embedder.embed_query(query)

        return release_retriever.retrieve(
            vector,
            limit=limit,
        )

    registry.register(
        "retrieve_issue",
        retrieve_issue,
    )

    registry.register(
        "retrieve_release",
        retrieve_release,
    )

    # ---------------------------------------------------------
    # Deterministic version verification
    # ---------------------------------------------------------

    def verify_version(
        actual_version: str,
        required_version: str,
        operation: str = "at_least",
    ) -> dict[str, Any]:
        """
        Verify versions deterministically.

        Supported operations:
        - at_least
        - compare
        """

        if operation == "at_least":
            result = version_verifier.is_at_least(
                actual_version,
                required_version,
            )

        elif operation == "compare":
            result = version_verifier.compare(
                actual_version,
                required_version,
            )

        else:
            raise ValueError(
                "Unsupported version operation. "
                "Use 'at_least' or 'compare'."
            )

        return {
            "valid": True,
            "operation": operation,
            "actual_version": actual_version,
            "required_version": required_version,
            "result": result,
        }

    registry.register(
        "verify_version",
        verify_version,
    )

    # ---------------------------------------------------------
    # Deterministic citation verification
    # ---------------------------------------------------------

    registry.register(
        "verify_citations",
        citation_verifier.verify_evidence_block,
    )

    return registry
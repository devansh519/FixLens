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
from urllib.parse import urlsplit

from src.embeddings.embedder import QueryEmbedder
from src.pipeline.router import ToolRouter
from src.retrieval.issue_retriever import IssueRetriever
from src.retrieval.release_retriever import ReleaseRetriever
from src.tools.citation_verifier import CitationVerifier
from src.tools.metadata_lookup import MetadataLookup
from src.tools.version_verifier import VersionVerifier
from src.vectorstore.qdrant_client import FixLensQdrantClient


def _repository_matches(
    record: Any,
    owner: str | None,
    repo: str | None,
) -> bool:
    if not owner and not repo:
        return True

    if repo and "/" in repo:
        repo_owner, repo_name = repo.split("/", 1)
        if owner and owner.casefold() != repo_owner.casefold():
            return False
        owner, repo = repo_owner, repo_name

    if isinstance(record, dict):
        issue = record.get("issue")
        pull_request = record.get("pull_request")
        commit = record.get("commit")
        release = record.get("release")
        version_info = record.get("version_info")
        evidence = record.get("evidence")
        payload = record.get("payload")
    else:
        issue = pull_request = commit = release = version_info = evidence = None
        payload = getattr(record, "payload", None)
    version_release = (
        version_info.get("release")
        if isinstance(version_info, dict)
        else None
    )
    payload_metadata = payload.get("metadata") if isinstance(payload, dict) else None
    urls = [
        issue.get("url") if isinstance(issue, dict) else None,
        pull_request.get("url") if isinstance(pull_request, dict) else None,
        commit.get("url") if isinstance(commit, dict) else None,
        release.get("url") if isinstance(release, dict) else None,
        version_release.get("html_url")
        if isinstance(version_release, dict)
        else None,
        evidence.get("issue_url") if isinstance(evidence, dict) else None,
        evidence.get("pr_url") if isinstance(evidence, dict) else None,
        payload_metadata.get("issue_url")
        if isinstance(payload_metadata, dict)
        else None,
        payload_metadata.get("pr_url")
        if isinstance(payload_metadata, dict)
        else None,
    ]
    for url in urls:
        if not isinstance(url, str):
            continue
        parts = [part for part in urlsplit(url).path.split("/") if part]
        if parts and parts[0] == "repos":
            parts = parts[1:]
        if len(parts) < 2:
            continue
        record_owner, record_repo = parts[0], parts[1]
        if (
            (not owner or record_owner.casefold() == owner.casefold())
            and (not repo or record_repo.casefold() == repo.casefold())
        ):
            return True
    return False


def _filter_repository(
    records: Any,
    owner: str | None,
    repo: str | None,
) -> Any:
    if not owner and not repo:
        return records
    if isinstance(records, (list, tuple)):
        return [
            record for record in records
            if _repository_matches(record, owner, repo)
        ]
    if isinstance(records, dict):
        return records if _repository_matches(records, owner, repo) else {}
    return records


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

    def lookup_issue(
        issue_number: int | str,
        owner: str | None = None,
        repo: str | None = None,
    ) -> Any:
        records = metadata.get_by_issue_number(int(issue_number))
        return _filter_repository(records, owner, repo)

    def lookup_pr(
        pr_number: int | str,
        owner: str | None = None,
        repo: str | None = None,
    ) -> Any:
        records = metadata.get_by_pr_number(int(pr_number))
        return _filter_repository(records, owner, repo)

    def lookup_commit(
        commit_sha: str,
        owner: str | None = None,
        repo: str | None = None,
    ) -> Any:
        records = metadata.get_by_commit_sha(str(commit_sha))
        return _filter_repository(records, owner, repo)

    def lookup_release(
        release_tag: str,
        owner: str | None = None,
        repo: str | None = None,
    ) -> Any:
        records = metadata.get_by_release_tag(str(release_tag))
        return _filter_repository(records, owner, repo)

    registry.register("lookup_issue", lookup_issue)
    registry.register("lookup_pr", lookup_pr)
    registry.register("lookup_commit", lookup_commit)
    registry.register("lookup_release", lookup_release)

    # ---------------------------------------------------------
    # Semantic retrieval tools
    # ---------------------------------------------------------

    def retrieve_issue(
        query: str,
        limit: int = retrieval_limit,
        owner: str | None = None,
        repo: str | None = None,
    ) -> list[Any]:
        """Retrieve relevant issue/PR records from Qdrant."""

        vector = query_embedder.embed_query(query)

        records = issue_retriever.retrieve(
            vector,
            limit=limit,
        )
        return _filter_repository(records, owner, repo)

    def retrieve_release(
        query: str,
        limit: int = retrieval_limit,
        owner: str | None = None,
        repo: str | None = None,
    ) -> list[Any]:
        """Retrieve relevant release records from Qdrant."""

        vector = query_embedder.embed_query(query)

        records = release_retriever.retrieve(
            vector,
            limit=limit,
        )
        return _filter_repository(records, owner, repo)

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
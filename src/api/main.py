"""FixLens Stage 6 FastAPI application wired to real Stage 4 tools."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agents.critic import create_critic
from src.agents.planner import create_planner
from src.pipeline.graph import FixLensGraph, build_fixlens_graph
from src.pipeline.tool_registry import build_real_tool_registry
from src.verification.verifier import create_verifier


app = FastAPI(
    title="FixLens",
    description="Agentic RAG for verifying GitHub issue fixes.",
    version="0.2.0",
)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)


class QueryResponse(BaseModel):
    query: str
    status: str
    answer: str
    verification: dict[str, Any] = {}


@lru_cache(maxsize=1)
def get_graph() -> FixLensGraph:
    metadata_path = os.getenv(
        "FIXLENS_METADATA_PATH",
        "storage/metadata/issue_pr_version.json",
    )
    registry = build_real_tool_registry(metadata_path=metadata_path)

    if registry.missing_actions():
        raise RuntimeError(
            "FixLens tool registry is incomplete: "
            + ", ".join(registry.missing_actions())
        )

    return build_fixlens_graph(
        planner=create_planner(),
        critic=create_critic(),
        router=registry.build_router(),
        verifier=create_verifier(),
        max_iterations=int(os.getenv("FIXLENS_MAX_ITERATIONS", "8")),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "fixlens"}


@app.get("/health/qdrant")
def qdrant_health() -> dict[str, bool]:
    from src.vectorstore.qdrant_client import FixLensQdrantClient

    healthy = FixLensQdrantClient().health_check()
    return {"qdrant": healthy}


@app.post("/api/v1/experience/query", response_model=QueryResponse)
def query_experience(request: QueryRequest) -> QueryResponse:
    try:
        result = get_graph().invoke(request.query)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"FixLens pipeline error: {type(exc).__name__}: {exc}",
        ) from exc

    return QueryResponse(
        query=request.query,
        status=str(result.get("status", "unknown")),
        answer=str(result.get("final_answer", "")),
        verification=result.get("verification", {}) or {},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("FIXLENS_API_HOST", "0.0.0.0"),
        port=int(os.getenv("FIXLENS_API_PORT", "8000")),
    )

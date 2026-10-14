"""Run auditable offline-baseline or live agentic FixLens evaluations."""

from __future__ import annotations

import argparse
import os
import re
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.metrics import compute_metrics
from evaluation.schema import (
    EvaluationCase,
    append_result_rows,
    load_dataset,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "eval" / "eval_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "evaluation" / "results" / "runs.jsonl"
_SECRET_PATTERN = re.compile(
    r"(?i)(?:gsk_[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._~-]+|"
    r"api[_-]?key[=:]\s*[^\s,;]+)"
)


def _safe_error(error: Exception) -> str:
    """Keep useful error types/messages while redacting token-shaped values."""
    message = _SECRET_PATTERN.sub("[REDACTED]", str(error))
    configured_key = os.getenv("GROQ_API_KEY")
    if configured_key:
        message = message.replace(configured_key, "[REDACTED]")
    return f"{type(error).__name__}: {message[:1000]}"


def _extract_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def visit(item: Any) -> None:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "payload") and not isinstance(item, dict):
            item = {"payload": item.payload}
        if isinstance(item, dict):
            records.append(item)
            for child in item.values():
                if isinstance(child, (dict, list)):
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return records


def _source_citations(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from src.tools.citation_verifier import CitationVerifier

    url_keys = {
        "url", "html_url", "issue_url", "pr_url", "commit_url", "release_url"
    }
    seen: set[str] = set()
    citations = []
    for record in _extract_records(evidence):
        for key, value in record.items():
            if key.casefold() not in url_keys or not isinstance(value, str):
                continue
            if value in seen:
                continue
            seen.add(value)
            number = record.get("number") or record.get("sha") or record.get("tag_name")
            citation = {
                "source": value,
                "source_type": key.removesuffix("_url"),
                "record_id": str(number or value.rsplit("/", 1)[-1]),
            }
            citations.append({
                **citation,
                "valid": CitationVerifier.validate_citation(citation),
            })
    return citations


def _outcome_from_result(result: dict[str, Any]) -> str:
    verification = result.get("verification", {})
    if verification.get("status") == "FIXED":
        return "fixed"
    records = _extract_records(verification.get("evidence", []))
    issue = next(
        (
            record["issue"]
            for record in records
            if isinstance(record.get("issue"), dict)
        ),
        None,
    )
    if issue and issue.get("state_reason") == "duplicate":
        return "duplicate"
    if issue and str(issue.get("state", "")).casefold() == "open":
        return "open"
    return "unknown"


def _prediction(result: dict[str, Any]) -> dict[str, Any]:
    verification = result.get("verification", {})
    evidence = verification.get("evidence", [])
    identifiers = {
        "fixing_pr": verification.get("verified_fixing_pr_number"),
        "merge_commit": verification.get("verified_merge_commit_sha"),
        "release": verification.get("verified_release_tag"),
        "version": verification.get("verified_version"),
    }
    claim_total = sum(value is not None for value in identifiers.values())
    records = _extract_records(evidence)
    supported = 0
    if identifiers["fixing_pr"] is not None and any(
        record.get("number") == identifiers["fixing_pr"]
        for record in records
    ):
        supported += 1
    if identifiers["merge_commit"] is not None and any(
        identifiers["merge_commit"] in (
            record.get("sha"),
            record.get("merge_commit_sha"),
            record.get("commit_sha"),
        )
        for record in records
    ):
        supported += 1
    if identifiers["release"] is not None and any(
        identifiers["release"] in (
            record.get("tag_name"),
            record.get("tag"),
            record.get("version"),
            record.get("version_name"),
        )
        for record in records
    ):
        supported += 1
    if identifiers["version"] is not None and any(
        identifiers["version"] in (
            record.get("version"),
            record.get("version_name"),
        )
        for record in records
    ):
        supported += 1
    return {
        "outcome": _outcome_from_result(result),
        **identifiers,
        "citations": _source_citations(evidence),
        "claim_support": {"supported": supported, "total": claim_total},
        "verification_status": verification.get("status"),
        "tool_error_count": len(verification.get("tool_errors", [])),
        "tool_errors": verification.get("tool_errors", []),
    }


def _build_runner(system: str, metadata_path: Path) -> Callable[[EvaluationCase], dict]:
    from src.pipeline.tool_registry import build_real_tool_registry
    from src.verification.verifier import VerificationEngine

    registry = build_real_tool_registry(metadata_path=metadata_path)
    router = registry.build_router()
    verifier = VerificationEngine()
    if system == "baseline":
        from src.baseline.naive_rag import NaiveRAGBaseline

        baseline = NaiveRAGBaseline(router, verifier)
        return lambda case: baseline.run(
            case.query,
            owner=case.repository.split("/", 1)[0],
            repo=case.repository.split("/", 1)[1],
        )
    if system != "agentic":
        raise ValueError(f"Unsupported evaluation system: {system}")

    from src.agents.critic import Critic
    from src.agents.planner import Planner
    from src.pipeline.graph import build_fixlens_graph

    graph = build_fixlens_graph(
        planner=Planner(),
        critic=Critic(),
        router=router,
        verifier=verifier,
        max_iterations=8,
    )
    return lambda case: graph.invoke(case.query)


def run_evaluation(
    dataset_path: str | Path = DEFAULT_DATASET,
    *,
    system: str,
    output_path: str | Path = DEFAULT_OUTPUT,
    case_ids: set[str] | None = None,
    max_cases: int | None = None,
    runner: Callable[[EvaluationCase], dict[str, Any]] | None = None,
    metadata_path: str | Path = ROOT / "storage" / "metadata" / "issue_pr_version.json",
) -> list[dict[str, Any]]:
    """Run cases and atomically append outcome rows, preserving earlier attempts."""
    cases = load_dataset(dataset_path)
    if case_ids is not None:
        unknown = case_ids - {case.case_id for case in cases}
        if unknown:
            raise ValueError(f"Unknown case IDs: {', '.join(sorted(unknown))}")
        cases = [case for case in cases if case.case_id in case_ids]
    if max_cases is not None:
        if max_cases < 1:
            raise ValueError("max_cases must be positive.")
        cases = cases[:max_cases]
    initialization_error = None
    try:
        execute = runner or _build_runner(system, Path(metadata_path))
    except Exception as exc:  # noqa: BLE001
        # Preserve initialization failures as explicit per-case result rows.
        execute = None
        initialization_error = exc
    run_id = str(uuid.uuid4())
    timestamp = datetime.now(UTC).isoformat()
    model = (
        os.getenv("FIXLENS_PLANNER_MODEL", "openai/gpt-oss-120b")
        if system == "agentic"
        else None
    )
    rows = []
    for case in cases:
        started = time.perf_counter()
        result: dict[str, Any]
        execution_status = "completed"
        error = None
        try:
            if initialization_error is not None:
                raise initialization_error
            if execute is None:
                raise RuntimeError("Evaluation runner initialization failed.")
            raw_result = execute(case)
            if hasattr(raw_result, "model_dump"):
                raw_result = raw_result.model_dump()
            if not isinstance(raw_result, dict):
                raise TypeError("Evaluation runner must return a dictionary.")
            result = raw_result
            state_results = result.get("tool_results", [])
            verification = result.get("verification", {})
            rows.append({
                "run_id": run_id,
                "timestamp": timestamp,
                "dataset_version": case.dataset_version,
                "system": system,
                "model": model,
                "case_id": case.case_id,
                "repository": case.repository,
                "issue_number": case.issue_number,
                "expected_outcome": case.expected_outcome,
                "expected_fixing_pr": case.expected_fixing_pr,
                "expected_merge_commit": case.expected_merge_commit,
                "expected_release": case.expected_release,
                "expected_version": case.expected_version,
                "prediction": _prediction({
                    "verification": verification,
                }),
                "execution_status": execution_status,
                "tool_calls": len(state_results),
                "iterations": result.get("iterations", 0),
                "latency_seconds": round(time.perf_counter() - started, 6),
            })
        except Exception as exc:  # noqa: BLE001
            # Record failed executions instead of dropping benchmark cases.
            execution_status = "error"
            error = _safe_error(exc)
            rows.append({
                "run_id": run_id,
                "timestamp": timestamp,
                "dataset_version": case.dataset_version,
                "system": system,
                "model": model,
                "case_id": case.case_id,
                "repository": case.repository,
                "issue_number": case.issue_number,
                "expected_outcome": case.expected_outcome,
                "expected_fixing_pr": case.expected_fixing_pr,
                "expected_merge_commit": case.expected_merge_commit,
                "expected_release": case.expected_release,
                "expected_version": case.expected_version,
                "prediction": {"outcome": "unknown", "citations": []},
                "execution_status": execution_status,
                "tool_calls": 0,
                "iterations": 0,
                "latency_seconds": round(time.perf_counter() - started, 6),
                "error": error,
            })

    append_result_rows(rows, output_path)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--system", choices=("agentic", "baseline"), required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument(
        "--metadata",
        type=Path,
        default=ROOT / "storage" / "metadata" / "issue_pr_version.json",
    )
    args = parser.parse_args()
    rows = run_evaluation(
        args.dataset,
        system=args.system,
        output_path=args.output,
        case_ids=set(args.case_ids) if args.case_ids else None,
        max_cases=args.max_cases,
        metadata_path=args.metadata,
    )
    print({
        "system": args.system,
        "cases_run": len(rows),
        "metrics": compute_metrics(rows),
        "output": str(args.output),
    })


if __name__ == "__main__":
    main()
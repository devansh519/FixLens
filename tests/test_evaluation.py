"""Tests for benchmark validation, metrics, and evaluation adapters."""

from __future__ import annotations

import json

import pytest

from evaluation.compare_baseline import compare_results
from evaluation.generate_eval_set import generate_dataset
from evaluation.metrics import compute_metrics
from evaluation.run_eval import run_evaluation
from evaluation.schema import EvaluationCase, load_dataset, write_dataset
from src.baseline.naive_rag import NaiveRAGBaseline
from src.pipeline.router import ToolRouter
from src.verification.verifier import VerificationEngine

FIXED_SHA = "c0ac53b7578b74dca8a10d12855f068499d82f0e"


def case_data(**overrides):
    values = {
        "case_id": "fixed-1",
        "dataset_version": "1.0.0",
        "repository": "pydantic/pydantic",
        "issue_number": 2142,
        "query": "Was pydantic/pydantic issue #2142 fixed?",
        "expected_outcome": "fixed",
        "expected_fixing_pr": 2143,
        "expected_merge_commit": FIXED_SHA,
        "expected_release": None,
        "expected_version": None,
        "evidence_refs": [
            "https://github.com/pydantic/pydantic/issues/2142",
            "https://github.com/pydantic/pydantic/pull/2143",
        ],
        "rationale": "The PR says it closes the issue and is merged.",
    }
    values.update(overrides)
    return values


def write_case_file(path, records):
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def test_dataset_schema_rejects_invalid_and_duplicate_cases(tmp_path):
    invalid = case_data(expected_merge_commit="not-a-sha")
    with pytest.raises(ValueError, match="expected_merge_commit"):
        EvaluationCase.model_validate(invalid)

    case = EvaluationCase.model_validate(case_data())
    dataset_path = tmp_path / "dataset.jsonl"
    with pytest.raises(ValueError, match="unique"):
        write_dataset([case, case], dataset_path)
    dataset_path.write_text(
        case.model_dump_json() + "\n" + case.model_dump_json() + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate case_id"):
        load_dataset(dataset_path)


def test_dataset_rejects_mixed_versions_and_unknown_fields(tmp_path):
    first = case_data()
    second = case_data(case_id="fixed-2", issue_number=2144, dataset_version="2.0.0")
    path = tmp_path / "dataset.jsonl"
    write_case_file(path, [first, second])
    with pytest.raises(ValueError, match="one dataset_version"):
        load_dataset(path)

    malformed = case_data(unexpected="not allowed")
    write_case_file(path, [malformed])
    with pytest.raises(ValueError, match="Invalid evaluation case"):
        load_dataset(path)


def test_metric_calculations_handle_classes_and_zero_denominators():
    rows = [
        {
            "expected_outcome": "fixed",
            "prediction": {
                "outcome": "fixed",
                "fixing_pr": 2143,
                "merge_commit": FIXED_SHA,
                "citations": [{"valid": True}],
                "claim_support": {"supported": 2, "total": 2},
            },
            "expected_fixing_pr": 2143,
            "expected_merge_commit": FIXED_SHA,
            "execution_status": "completed",
            "tool_calls": 3,
            "iterations": 1,
            "latency_seconds": 2.0,
        },
        {
            "expected_outcome": "open",
            "prediction": {"outcome": "fixed", "citations": [{"valid": False}]},
            "execution_status": "error",
            "error": "RateLimitError",
        },
        {
            "expected_outcome": "duplicate",
            "prediction": {"outcome": "duplicate"},
            "execution_status": "completed",
            "tool_calls": 1,
        },
        {
            "expected_outcome": "unknown",
            "prediction": {"outcome": "unknown"},
            "execution_status": "completed",
        },
    ]
    metrics = compute_metrics(rows)
    assert metrics["accuracy"] == 0.75
    assert metrics["confusion_matrix"]["open"]["fixed"] == 1
    assert metrics["fix_verification"]["fixed_claim_precision"] == 0.5
    assert metrics["fix_verification"]["false_positive_fix_rate"] == pytest.approx(1 / 3)
    assert metrics["fix_verification"]["fix_verification_recall"] == 1.0
    assert metrics["entity_identification"]["pr_accuracy"] == 1.0
    assert metrics["entity_identification"]["version_accuracy"] is None
    assert metrics["evidence_quality"]["citation_validity_rate"] == 0.5
    assert metrics["evidence_quality"]["evidence_supported_claim_rate"] == 1.0
    assert metrics["operations"]["execution_success_rate"] == 0.75
    assert metrics["operations"]["average_latency_seconds"] == 2.0

    empty = compute_metrics([])
    assert empty["evaluated_case_count"] == 0
    assert empty["accuracy"] is None
    assert empty["entity_identification"]["release_version_accuracy"] is None


def test_naive_rag_baseline_uses_router_and_deterministic_verifier():
    router = ToolRouter({
        "retrieve_issue": lambda query, owner, repo: [{
            "issue": {
                "number": 11151,
                "state": "open",
                "url": "https://github.com/pydantic/pydantic/issues/11151",
            }
        }]
    })
    baseline = NaiveRAGBaseline(router, VerificationEngine())

    result = baseline.run("Was issue #11151 fixed?", owner="pydantic", repo="pydantic")

    assert result["verification"]["issue_verified"] is True
    assert result["iterations"] == 1
    assert result["tool_results"][0]["success"] is True


def test_runner_preserves_failed_attempts_and_redacts_tokens(tmp_path):
    case = EvaluationCase.model_validate(case_data())
    dataset_path = tmp_path / "dataset.jsonl"
    write_dataset([case], dataset_path)
    output_path = tmp_path / "results.jsonl"

    failed = run_evaluation(
        dataset_path,
        system="agentic",
        output_path=output_path,
        runner=lambda _: (_ for _ in ()).throw(RuntimeError("gsk_abcdefghijklmnopqrstuvwxyz")),
    )
    assert failed[0]["execution_status"] == "error"
    assert "gsk_" not in failed[0]["error"]

    succeeded = run_evaluation(
        dataset_path,
        system="agentic",
        output_path=output_path,
        case_ids={"fixed-1"},
        runner=lambda _: {"verification": {"status": "INSUFFICIENT_EVIDENCE"}},
    )
    stored = load_result_rows(output_path)
    assert len(stored) == 2
    assert stored[0]["execution_status"] == "error"
    assert stored[1]["execution_status"] == "completed"
    assert succeeded[0]["case_id"] == "fixed-1"


def test_runner_rejects_malformed_predictions_without_losing_case_record(tmp_path):
    case = EvaluationCase.model_validate(case_data())
    dataset_path = tmp_path / "dataset.jsonl"
    write_dataset([case], dataset_path)
    output_path = tmp_path / "results.jsonl"
    rows = run_evaluation(
        dataset_path,
        system="baseline",
        output_path=output_path,
        runner=lambda _: ["not", "a", "result"],
    )

    assert rows[0]["execution_status"] == "error"
    assert rows[0]["prediction"]["outcome"] == "unknown"


def test_runner_passes_query_not_ground_truth_to_system(tmp_path):
    case = EvaluationCase.model_validate(case_data())
    dataset_path = tmp_path / "dataset.jsonl"
    write_dataset([case], dataset_path)
    received = []
    run_evaluation(
        dataset_path,
        system="baseline",
        output_path=tmp_path / "results.jsonl",
        runner=lambda value: received.append(value.query) or {
            "verification": {"status": "INSUFFICIENT_EVIDENCE"}
        },
    )
    assert received == [case.query]


def test_evaluation_set_generator_builds_versioned_benchmark(tmp_path):
    for name, outcome, record in (
        ("fixed.jsonl", "fixed", case_data()),
        ("open.jsonl", "open", case_data(
            case_id="open-1", issue_number=11151, expected_outcome="open",
            expected_fixing_pr=None, expected_merge_commit=None,
        )),
    ):
        write_case_file(tmp_path / name, [record])

    (tmp_path / "duplicate.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "unknown.jsonl").write_text("", encoding="utf-8")
    output = tmp_path / "eval_dataset.jsonl"
    cases, counts = generate_dataset(
        tmp_path,
        output,
        dataset_version="1.0.0",
    )

    assert len(cases) == 2
    assert counts == {"fixed": 1, "open": 1}
    assert [case.case_id for case in load_dataset(output)] == [
        "fixed-1",
        "open-1",
    ]


def test_baseline_comparison_requires_same_cases_and_ground_truth():
    base = {
        "case_id": "x",
        "dataset_version": "1.0.0",
        "repository": "pydantic/pydantic",
        "issue_number": 2142,
        "expected_outcome": "open",
        "expected_fixing_pr": None,
        "expected_merge_commit": None,
        "expected_release": None,
        "expected_version": None,
        "prediction": {"outcome": "open"},
        "execution_status": "completed",
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    report = compare_results([base], [base])
    assert report["case_count"] == 1
    assert report["agentic_minus_baseline"]["accuracy"] == 0.0
    assert "too small" in report["interpretation"]

    with pytest.raises(ValueError, match="identical case IDs"):
        compare_results([base], [])
    different_dataset = {**base, "dataset_version": "0.9.0"}
    with pytest.raises(ValueError, match="Dataset version or ground truth"):
        compare_results([base], [different_dataset])


def load_result_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

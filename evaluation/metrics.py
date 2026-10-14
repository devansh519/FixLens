"""Outcome, fix-chain, evidence, and operational evaluation metrics."""

from __future__ import annotations

from typing import Any

OUTCOMES = ("fixed", "open", "duplicate", "unknown")


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _prediction(row: dict[str, Any]) -> dict[str, Any]:
    prediction = row.get("prediction", {})
    if isinstance(prediction, str):
        return {"outcome": prediction}
    return prediction if isinstance(prediction, dict) else {}


def _average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute denominator-aware metrics over per-case result rows."""
    confusion = {
        actual: {predicted: 0 for predicted in OUTCOMES}
        for actual in OUTCOMES
    }
    correct = invalid_labels = 0
    for row in rows:
        actual = row.get("expected_outcome")
        predicted = _prediction(row).get("outcome")
        if actual not in OUTCOMES or predicted not in OUTCOMES:
            invalid_labels += 1
            continue
        confusion[actual][predicted] += 1
        correct += actual == predicted

    per_class: dict[str, dict[str, float | int | None]] = {}
    for label in OUTCOMES:
        tp = confusion[label][label]
        fp = sum(
            confusion[other][label]
            for other in OUTCOMES
            if other != label
        )
        fn = sum(
            confusion[label][other]
            for other in OUTCOMES
            if other != label
        )
        precision = _ratio(tp, tp + fp)
        recall = _ratio(tp, tp + fn)
        if precision is not None and recall is not None:
            f1 = (
                2 * precision * recall / (precision + recall)
                if precision + recall
                else 0.0
            )
        elif precision == 0 or recall == 0:
            f1 = 0.0
        else:
            f1 = None
        per_class[label] = {
            "support": tp + fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    macro_values = [
        value["f1"] for value in per_class.values()
        if value["f1"] is not None
    ]
    positive = negative = false_positive = 0
    pr_correct = pr_total = commit_correct = commit_total = 0
    release_correct = release_total = version_correct = version_total = 0
    citations_valid = citations_total = 0
    supported_claims = total_claims = 0
    completed = execution_errors = tool_errors = unresolved = 0
    tool_counts: list[float] = []
    iteration_counts: list[float] = []
    latencies: list[float] = []

    for row in rows:
        expected = row.get("expected_outcome")
        predicted = _prediction(row)
        outcome = predicted.get("outcome")
        if expected == "fixed":
            positive += 1
        elif expected in OUTCOMES:
            negative += 1
            false_positive += outcome == "fixed"

        expected_entities = (
            ("expected_fixing_pr", "fixing_pr", "pr"),
            ("expected_merge_commit", "merge_commit", "commit"),
            ("expected_release", "release", "release"),
        )
        for expected_key, predicted_key, entity in expected_entities:
            expected_value = row.get(expected_key)
            if expected_value is None:
                continue
            actual_value = predicted.get(predicted_key)
            if entity == "pr":
                pr_total += 1
                pr_correct += actual_value == expected_value
            elif entity == "commit":
                commit_total += 1
                commit_correct += (
                    isinstance(actual_value, str)
                    and actual_value.lower() == expected_value.lower()
                )
            elif entity == "release":
                release_total += 1
                release_correct += actual_value == expected_value
        expected_version = row.get("expected_version")
        if expected_version is not None:
            version_total += 1
            version_correct += predicted.get("version") == expected_version

        for citation in predicted.get("citations", []):
            if isinstance(citation, dict) and isinstance(citation.get("valid"), bool):
                citations_total += 1
                citations_valid += citation["valid"]
        claim_support = predicted.get("claim_support", {})
        if isinstance(claim_support, dict):
            supported_claims += int(claim_support.get("supported", 0))
            total_claims += int(claim_support.get("total", 0))

        status = row.get("execution_status")
        completed += status == "completed"
        execution_errors += status == "error"
        tool_errors += bool(_prediction(row).get("tool_error_count", 0))
        unresolved += outcome in {"open", "duplicate", "unknown"}
        for key, target in (
            ("tool_calls", tool_counts),
            ("iterations", iteration_counts),
            ("latency_seconds", latencies),
        ):
            value = row.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                target.append(float(value))

    fixed_tp = sum(
        row.get("expected_outcome") == "fixed"
        and _prediction(row).get("outcome") == "fixed"
        for row in rows
    )
    fixed_predictions = sum(
        _prediction(row).get("outcome") == "fixed" for row in rows
    )
    return {
        "evaluated_case_count": len(rows) - invalid_labels,
        "invalid_label_rows": invalid_labels,
        "accuracy": _ratio(correct, len(rows) - invalid_labels),
        "per_class": per_class,
        "macro_f1": _ratio(sum(macro_values), len(macro_values)),
        "confusion_matrix": confusion,
        "fix_verification": {
            "fixed_claim_precision": _ratio(fixed_tp, fixed_predictions),
            "false_positive_fix_rate": _ratio(false_positive, negative),
            "fix_verification_recall": _ratio(fixed_tp, positive),
            "verified_fixed_cases": fixed_tp,
            "false_positive_fixed_cases": false_positive,
        },
        "entity_identification": {
            "pr_accuracy": _ratio(pr_correct, pr_total),
            "pr_cases": pr_total,
            "merge_commit_accuracy": _ratio(commit_correct, commit_total),
            "merge_commit_cases": commit_total,
            "release_version_accuracy": _ratio(release_correct, release_total),
            "release_version_cases": release_total,
            "version_accuracy": _ratio(version_correct, version_total),
            "version_cases": version_total,
        },
        "evidence_quality": {
            "citation_validity_rate": _ratio(citations_valid, citations_total),
            "valid_citations": citations_valid,
            "evaluated_citations": citations_total,
            "evidence_supported_claim_rate": _ratio(
                supported_claims, total_claims
            ),
            "supported_claims": supported_claims,
            "evaluated_claims": total_claims,
        },
        "operations": {
            "execution_success_rate": _ratio(completed, len(rows)),
            "execution_error_rate": _ratio(execution_errors, len(rows)),
            "tool_error_rate": _ratio(tool_errors, len(rows)),
            "unresolved_rate": _ratio(unresolved, len(rows)),
            "average_tool_calls": _average(tool_counts),
            "average_iterations": _average(iteration_counts),
            "average_latency_seconds": _average(latencies),
        },
    }
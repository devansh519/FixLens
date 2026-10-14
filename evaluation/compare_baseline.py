"""Compare FixLens and the direct-retrieval baseline on identical cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.metrics import compute_metrics
from evaluation.schema import read_result_rows


def compare_results(
    agentic_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return both metric sets and signed differences on shared case IDs."""
    def latest_by_case(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        selected: dict[str, dict[str, Any]] = {}
        for row in rows:
            case_id = row.get("case_id")
            if not isinstance(case_id, str):
                raise TypeError("Every result row must contain a case_id.")
            previous = selected.get(case_id)
            if previous is None or str(row.get("timestamp", "")) >= str(
                previous.get("timestamp", "")
            ):
                selected[case_id] = row
        return selected

    agentic = latest_by_case(agentic_rows)
    baseline = latest_by_case(baseline_rows)
    if agentic.keys() != baseline.keys():
        raise ValueError("Agentic and baseline runs must cover identical case IDs.")
    comparable_fields = (
        "dataset_version",
        "repository",
        "issue_number",
        "expected_outcome",
        "expected_fixing_pr",
        "expected_merge_commit",
        "expected_release",
        "expected_version",
    )
    for case_id in agentic:
        if any(
            agentic[case_id].get(field) != baseline[case_id].get(field)
            for field in comparable_fields
        ):
            raise ValueError(
                f"Dataset version or ground truth differs for case {case_id}."
            )

    agentic_metrics = compute_metrics(list(agentic.values()))
    baseline_metrics = compute_metrics(list(baseline.values()))
    differences = _numeric_differences(agentic_metrics, baseline_metrics)
    return {
        "case_count": len(agentic),
        "interpretation": (
            "Descriptive only; this benchmark is too small for claims of "
            "statistical significance."
        ),
        "agentic": agentic_metrics,
        "baseline": baseline_metrics,
        "agentic_minus_baseline": differences,
        "case_differences": [
            {
                "case_id": case_id,
                "expected": agentic[case_id].get("expected_outcome"),
                "agentic": agentic[case_id].get("prediction", {}).get("outcome"),
                "baseline": baseline[case_id].get("prediction", {}).get("outcome"),
            }
            for case_id in sorted(agentic)
            if agentic[case_id].get("prediction", {}).get("outcome")
            != baseline[case_id].get("prediction", {}).get("outcome")
        ],
    }


def _numeric_differences(
    first: dict[str, Any],
    second: dict[str, Any],
    prefix: str = "",
) -> dict[str, float | None]:
    differences: dict[str, float | None] = {}
    for key, value in first.items():
        other = second.get(key)
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and isinstance(other, dict):
            differences.update(_numeric_differences(value, other, path))
        elif (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and isinstance(other, (int, float))
            and not isinstance(other, bool)
        ):
            differences[path] = value - other
    return differences


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agentic-results", type=Path, required=True)
    parser.add_argument("--baseline-results", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare_results(
        read_result_rows(args.agentic_results),
        read_result_rows(args.baseline_results),
    )
    serialized = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
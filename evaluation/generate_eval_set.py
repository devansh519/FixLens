"""Build the normalized, versioned JSONL benchmark from curated label files."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from evaluation.schema import EvaluationCase, write_dataset

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = {
    "fixed": "fixed.jsonl",
    "open": "open.jsonl",
    "duplicate": "duplicate.jsonl",
    "unknown": "unknown.jsonl",
}


def generate_dataset(
    source_dir: str | Path = ROOT / "data" / "eval",
    output_path: str | Path = ROOT / "data" / "eval" / "eval_dataset.jsonl",
    *,
    dataset_version: str,
) -> tuple[list[EvaluationCase], dict[str, int]]:
    """Validate category-specific curation files and write combined JSONL."""
    source = Path(source_dir)
    cases: list[EvaluationCase] = []
    for outcome, filename in SOURCE_FILES.items():
        path = source / filename
        if not path.exists():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = EvaluationCase.model_validate_json(line)
            except Exception as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
            if value.expected_outcome != outcome:
                raise ValueError(
                    f"{path}:{line_number}: expected_outcome must be {outcome!r}."
                )
            if value.dataset_version != dataset_version:
                raise ValueError(
                    f"{path}:{line_number}: dataset_version must be "
                    f"{dataset_version!r}."
                )
            cases.append(value)
    if not cases:
        raise ValueError("No curated evaluation cases were found.")
    write_dataset(cases, output_path)
    return cases, dict(Counter(case.expected_outcome for case in cases))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "data" / "eval")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "eval" / "eval_dataset.jsonl",
    )
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    cases, composition = generate_dataset(
        args.source_dir,
        args.output,
        dataset_version=args.version,
    )
    print({
        "dataset_version": args.version,
        "case_count": len(cases),
        "composition": composition,
        "output": str(args.output),
    })


if __name__ == "__main__":
    main()
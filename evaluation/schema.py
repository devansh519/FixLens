"""Schema and I/O helpers for the FixLens evaluation dataset."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Outcome = Literal["fixed", "open", "duplicate", "unknown"]
_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")


class EvaluationCase(BaseModel):
    """A single, source-anchored ground-truth case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    repository: str
    issue_number: int = Field(strict=True, gt=0)
    query: str = Field(min_length=1)
    expected_outcome: Outcome
    expected_fixing_pr: int | None = Field(default=None, strict=True, gt=0)
    expected_merge_commit: str | None = None
    expected_release: str | None = None
    expected_version: str | None = None
    evidence_refs: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        if not _REPOSITORY_PATTERN.fullmatch(value):
            raise ValueError("repository must be written as owner/repo.")
        return value

    @field_validator("query", "rationale")
    @classmethod
    def validate_non_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank.")
        return value.strip()

    @field_validator("expected_merge_commit")
    @classmethod
    def validate_merge_commit(cls, value: str | None) -> str | None:
        if value is not None and not _COMMIT_PATTERN.fullmatch(value):
            raise ValueError("expected_merge_commit must be a hexadecimal SHA.")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, values: list[str]) -> list[str]:
        if not values or any(
            not re.fullmatch(r"https://github\.com/[^/\s]+/[^/\s]+/.+", value)
            for value in values
        ):
            raise ValueError("evidence_refs must contain GitHub source URLs.")
        return values

    @model_validator(mode="after")
    def validate_expected_chain(self) -> EvaluationCase:
        if self.expected_outcome == "fixed":
            if not self.expected_fixing_pr or not self.expected_merge_commit:
                raise ValueError(
                    "fixed cases require a verified fixing PR and merge commit."
                )
        elif any((
            self.expected_fixing_pr is not None,
            self.expected_merge_commit is not None,
            self.expected_release is not None,
            self.expected_version is not None,
        )):
            raise ValueError(
                "non-fixed cases cannot include an expected fix-chain entity."
            )
        return self


def load_dataset(path: str | Path) -> list[EvaluationCase]:
    """Load and validate a JSONL dataset; reject duplicates and mixed versions."""
    dataset_path = Path(path)
    cases: list[EvaluationCase] = []
    seen_ids: set[str] = set()
    versions: set[str] = set()
    with dataset_path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                case = EvaluationCase.model_validate_json(line)
            except Exception as exc:
                raise ValueError(
                    f"Invalid evaluation case on line {line_number}: {exc}"
                ) from exc
            if case.case_id in seen_ids:
                raise ValueError(f"Duplicate case_id: {case.case_id}")
            seen_ids.add(case.case_id)
            versions.add(case.dataset_version)
            cases.append(case)
    if len(versions) > 1:
        raise ValueError("All evaluation cases must use one dataset_version.")
    return cases


def write_dataset(
    cases: list[EvaluationCase],
    path: str | Path,
) -> None:
    """Atomically write normalized JSONL after validating dataset-wide rules."""
    case_ids = [case.case_id for case in cases]
    versions = {case.dataset_version for case in cases}
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Evaluation case IDs must be unique.")
    if len(versions) > 1:
        raise ValueError("All evaluation cases must use one dataset_version.")

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(
        case.model_dump_json() + "\n"
        for case in cases
    )
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary_name, destination)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def read_result_rows(path: str | Path) -> list[dict]:
    """Read JSONL result rows and reject malformed entries."""
    result_path = Path(path)
    if not result_path.exists():
        return []
    rows = []
    with result_path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid result JSON on line {line_number}."
                ) from exc
            if not isinstance(value, dict):
                raise TypeError(f"Result on line {line_number} must be an object.")
            rows.append(value)
    return rows


def append_result_rows(
    rows: list[dict],
    path: str | Path,
) -> None:
    """Append result attempts atomically while preserving earlier runs."""
    destination = Path(path)
    existing = read_result_rows(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
        for row in [*existing, *rows]
    )
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary_name, destination)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MetadataLookup:
    """Lookup issue, PR, commit, and release metadata."""

    def __init__(self, metadata_path: str | Path) -> None:
        self.metadata_path = Path(metadata_path)

        if not self.metadata_path.exists():
            raise FileNotFoundError(
                f"Metadata file not found: {self.metadata_path}"
            )

        self.records = self._load_records()

    def _load_records(self) -> list[dict[str, Any]]:
        """Load a JSON array, JSON object, or JSONL file."""
        content = self.metadata_path.read_text(
            encoding="utf-8"
        ).strip()

        if not content:
            return []

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            records = []

            for line_number, line in enumerate(
                content.splitlines(),
                start=1,
            ):
                line = line.strip()

                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSON on line {line_number}"
                    ) from exc

                if not isinstance(record, dict):
                    raise ValueError(
                        f"Expected an object on line {line_number}"
                    )

                records.append(record)

            return records

        if isinstance(parsed, list):
            return [
                record
                for record in parsed
                if isinstance(record, dict)
            ]

        if isinstance(parsed, dict):
            for key in ("records", "items", "data", "mappings"):
                if isinstance(parsed.get(key), list):
                    return [
                        record
                        for record in parsed[key]
                        if isinstance(record, dict)
                    ]

            return [parsed]

        raise ValueError("Unsupported metadata format.")

    def get_by_issue_number(
        self,
        issue_number: int,
    ) -> list[dict[str, Any]]:
        """Find records by nested issue number."""
        return [
            record
            for record in self.records
            if record.get("issue", {}).get("number") == issue_number
        ]

    def get_by_pr_number(
        self,
        pr_number: int,
    ) -> list[dict[str, Any]]:
        """Find records by nested pull-request number."""
        return [
            record
            for record in self.records
            if record.get("pull_request", {}).get("number") == pr_number
        ]

    def get_by_commit_sha(
        self,
        commit_sha: str,
    ) -> list[dict[str, Any]]:
        """Find records by PR merge commit SHA."""
        expected_sha = commit_sha.lower()

        matches = []

        for record in self.records:
            pull_request = record.get("pull_request", {})
            evidence = record.get("evidence", {})

            candidate_shas = {
                pull_request.get("merge_commit_sha"),
                evidence.get("merge_commit_sha"),
            }

            candidate_shas = {
                sha.lower()
                for sha in candidate_shas
                if isinstance(sha, str)
            }

            if expected_sha in candidate_shas:
                matches.append(record)

        return matches

    def get_by_release_tag(
        self,
        release_tag: str,
    ) -> list[dict[str, Any]]:
        """Find records by resolved release tag."""
        expected_tag = release_tag.lower()

        matches = []

        for record in self.records:
            version_info = record.get("version_info", {})

            tag_name = version_info.get("tag_name")

            if isinstance(tag_name, str):
                if tag_name.lower() == expected_tag:
                    matches.append(record)

        return matches

    def get_by_issue_and_pr(
        self,
        issue_number: int,
        pr_number: int,
    ) -> list[dict[str, Any]]:
        """Find records matching both an issue and pull request."""
        return [
            record
            for record in self.records
            if (
                record.get("issue", {}).get("number") == issue_number
                and record.get("pull_request", {}).get("number") == pr_number
            )
        ]

    def get_linked_evidence(
        self,
        issue_number: int,
    ) -> dict[str, Any] | None:
        """
        Return the evidence chain for an issue.

        Returns None if the issue does not exist.
        """
        records = self.get_by_issue_number(issue_number)

        if not records:
            return None

        record = records[0]

        return {
            "issue": record.get("issue"),
            "pull_request": record.get("pull_request"),
            "version_info": record.get("version_info"),
            "evidence": record.get("evidence"),
        }
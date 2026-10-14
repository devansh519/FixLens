# FixLens Data Model

## Evidence entities

| Entity | Identity | Relevant facts |
|---|---|---|
| Issue | `(repository, issue_number)` | State, state reason, title/body, URL, comments |
| Pull request | `(repository, pr_number)` | State, merge timestamp, merge commit SHA, URL, title/body |
| Commit | Repository plus full SHA | Commit identity and relationship to the merged PR |
| Release/tag | `(repository, tag)` | Published release and version information |
| Tool observation | Action plus parameters and result | Success/failure, returned records, and tool error type |

Repository is part of issue and PR identity. Numeric issue/PR IDs alone are
not globally unique and must never be used to associate records from different
repositories.

## Stored artifacts

- `data/raw/issues/`, `comments/`, `prs/`, `releases/`, and `tags/` contain
  GitHub API page or record snapshots.
- `data/processed/mappings.jsonl` contains repository-scoped issue-to-PR
  references. `version_mappings.jsonl` contains release/version associations.
- `storage/metadata/issue_pr_version.json` contains the normalized records
  consumed by tools. This is generated data and is git-ignored.
- Processed chunks and vector indexes are stored under `data/processed/` and
  the local Qdrant collections `issues_prs` and `releases`.
- The small curated evaluation corpus lives in the tracked
  `data/eval/*.jsonl` files; evaluation run output is local under
  `evaluation/results/`.

## Verification semantics

The deterministic verifier emits a `VerificationResult` containing the
overall status, per-link verification flags, identifiers that were actually
verified, evidence records, and tool-error types. A fixing PR and merge commit
are exposed only when the PR-to-issue relation, merge, and commit are
verified. A release tag/version is exposed only when the release record
supports it.

Failed tool observations are retained in `tool_errors` but excluded from
evidence. A missing PR/release is not interpreted as a negative fact; the
result remains `NOT_VERIFIED` or `INSUFFICIENT_EVIDENCE` as appropriate.
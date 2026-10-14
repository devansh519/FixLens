# FixLens Evaluation

## Benchmark format and curation

The tracked benchmark is JSONL, with one strict `EvaluationCase` per line.
`data/eval/fixed.jsonl`, `open.jsonl`, `duplicate.jsonl`, and `unknown.jsonl`
are category-specific source files. The generator checks that each record's
label matches its source file and that all records use one dataset version.
The combined dataset is `data/eval/eval_dataset.jsonl`.

Each case contains a stable ID, dataset version, repository, issue number,
query, expected outcome, optional expected fix-chain entities, source URLs,
and a short ground-truth rationale. Fixed cases must include an evidenced
fixing PR and merge commit. Release/version fields are optional because they
must not be guessed. Dataset validation rejects duplicate IDs, mixed versions,
malformed URLs, unknown fields, and inconsistent fixed-case records.

Regenerate the combined file after editing a category file:

```powershell
uv run python -m evaluation.generate_eval_set --version 1.0.0
```

The evaluation runner passes only the query to the system; labels and expected
entities are not passed to either system. The agentic runner uses the normal
Planner/Critic/Router/Verifier graph. The baseline retrieves once and applies
the same deterministic verifier, omitting the planning loop.

## Running

Evaluation requires the curated dataset and local FixLens metadata/indexes.
The agentic system additionally requires `GROQ_API_KEY`; both systems require
the retrieval backend. Run each system to a separate results file:

```powershell
uv run python -m evaluation.run_eval --system agentic `
  --output evaluation/results/agentic.jsonl
uv run python -m evaluation.run_eval --system baseline `
  --output evaluation/results/baseline.jsonl
uv run python -m evaluation.compare_baseline `
  --agentic-results evaluation/results/agentic.jsonl `
  --baseline-results evaluation/results/baseline.jsonl
```

Use `--case-id` more than once or `--max-cases` for a scoped run. Result rows
include run/dataset/system metadata, predictions, execution status, tool-call
count, iterations, latency, and a sanitized error for failed cases. Runs append
atomically, retaining earlier attempts. Comparison uses the latest result per
case and requires identical case IDs and ground truth. Keep run files local;
they are git-ignored, except the explicitly retained
`evaluation/results/baseline-v1.0.0.jsonl` benchmark artifact.

## Metrics

- **Outcome classification:** accuracy, per-class precision/recall/F1,
  macro-F1, and confusion matrix over `fixed`, `open`, `duplicate`, and
  `unknown`.
- **Fix verification:** precision of fixed claims, false-positive fixed rate
  over non-fixed cases, and recall over fixed cases.
- **Entity identification:** accuracy for expected fixing PR, merge commit,
  release tag, and version. An entity with no applicable ground-truth cases
  has a `null` metric rather than a fabricated zero.
- **Evidence quality:** citation URL validity and the proportion of claimed
  entities found in returned evidence records.
- **Operations:** per-case execution/tool error rates, unresolved rate, and
  average tool calls, iterations, and latency.

Execution errors are recorded as `unknown` predictions and are also reported
separately; they are not silently dropped from operational metrics.

## Interpretation limits

The current dataset is intentionally small and uses one repository. Its
agentic-vs-baseline comparison is descriptive only, not a statistically
significant quality claim. Expand the independently curated cases and
repositories before drawing general conclusions.
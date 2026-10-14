# FixLens

**Look beyond the issue. Verify the fix.**

FixLens answers evidence-backed questions about GitHub issues and their
possible fixes. The system uses an LLM to choose investigative actions,
deterministic GitHub tools to collect records, and a deterministic verifier to
decide what the evidence supports. It reports missing evidence as unresolved
instead of inventing a pull request, commit, release, or version.

## Setup

Requirements: Python 3.12, [`uv`](https://docs.astral.sh/uv/), a reachable
Qdrant instance, and GitHub/Groq credentials for live operation. Install the
project dependencies:

```powershell
uv sync
```

Set `GITHUB_TOKEN` and `GROQ_API_KEY` in a local `.env` file; do not commit
credentials. Retrieval uses Qdrant at `localhost:6333` by default, configurable
with `QDRANT_HOST`, `QDRANT_PORT`, or `QDRANT_URL`. Select the repository in
`config/repos.yaml`, then populate its local data and index:

```powershell
uv run python -m src.ingestion.run_ingestion
uv run python -m src.indexing.run_indexing
```

Run the API with `uv run python -m src.api.main`. It exposes `/health`,
`/health/qdrant`, and `POST /api/v1/experience/query`. Run the offline tests
with `uv run pytest -q`; the real-data end-to-end test also requires live
services and available API quota.

## Architecture

The Planner proposes an action, the Router dispatches it to a registered
deterministic tool, and tool observations persist in graph state. The Critic
can request further evidence; bounded progress and repeated-action checks
prevent unproductive loops. The Verifier makes conservative fix-chain
decisions from the collected evidence. See [architecture](docs/architecture.md)
and [data model](docs/data_model.md) for details.

## Curated evaluation

Benchmark v1.0.0 contains four manually curated Pydantic cases:

| Issue | Expected outcome | Ground-truth evidence |
|---|---|---|
| [pydantic/pydantic#2142](https://github.com/pydantic/pydantic/issues/2142) | Fixed | PR #2143, merge commit `c0ac53b7578b74dca8a10d12855f068499d82f0e`, release `v1.8` / version `1.8` |
| [pydantic/pydantic#11151](https://github.com/pydantic/pydantic/issues/11151) | Open / not verified fixed | No closing PR is evidenced; PR #3552 concerns `python/mypy#11151` |
| [pydantic/pydantic#13739](https://github.com/pydantic/pydantic/issues/13739) | Duplicate | GitHub marks the issue `state_reason=duplicate` |
| [pydantic/pydantic#10289](https://github.com/pydantic/pydantic/issues/10289) | Unknown | Closed as not planned; no fixing PR is evidenced |

For #2142, the issue-to-PR link, merged PR, merge commit, and inclusion in
`v1.8` have been checked against GitHub evidence. For #11151, the issue is
still open and no same-repository closing PR supports a fix claim. See the
full evidence notes and source links in [evaluation results](docs/results.md).

## Measured results and limitations

The retrieval-only baseline below is the latest local run on the same four
v1.0.0 cases, retained at
[`evaluation/results/baseline-v1.0.0.jsonl`](evaluation/results/baseline-v1.0.0.jsonl).
The agentic evaluation has not completed: Groq returned a daily
token-quota rate limit. Therefore there is no valid baseline-versus-agentic
comparison yet.

| Metric | Baseline | Agentic |
|---|---:|---:|
| Accuracy | 0.25 (1/4) | Not measured |
| Macro-F1 | 0.10 | Not measured |
| False-positive fixed rate | 0.00 (0/3) | Not measured |
| Fixed-claim precision | N/A (no fixed claims) | Not measured |
| Citation URL validity | 1.00 (31/31) | Not measured |
| Execution completion | 1.00 (4/4) | Not measured |
| Mean latency | 4.395075 seconds | Not measured |
| API cost | Not recorded | Not recorded |

The benchmark has only four cases from one repository, so the metrics are
descriptive, not statistically meaningful. Citation validity checks URL
syntax, not whether the cited content substantively proves a claim. The
evaluation output does not capture token usage, so API cost cannot be
calculated. See [evaluation methodology](docs/evaluation.md) for metric
definitions and denominators.

## Reproducing or resuming evaluation

The benchmark and category source files are versioned; the frozen baseline
result is retained at the path above. New evaluation artifacts are written
locally under `evaluation/results/`.
Run the agentic system once Groq quota is available:

```powershell
uv run python -m evaluation.run_eval --dataset data/eval/eval_dataset.jsonl --system agentic --output evaluation/results/agentic.jsonl
```

Then compare it with the existing same-dataset baseline:

```powershell
uv run python -m evaluation.compare_baseline --agentic-results evaluation/results/agentic.jsonl --baseline-results evaluation/results/baseline-v1.0.0.jsonl --output evaluation/results/comparison.json
```

See [evaluation documentation](docs/evaluation.md) for dataset regeneration,
CLI options, and interpretation limits.

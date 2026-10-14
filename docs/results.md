# FixLens Evaluation Results

## Benchmark v1.0.0

The current curated set contains four Pydantic issue cases:

| Expected outcome | Case | Ground-truth note |
|---|---|---|
| `fixed` | [pydantic/pydantic#2142](https://github.com/pydantic/pydantic/issues/2142) | Merged [PR #2143](https://github.com/pydantic/pydantic/pull/2143); merge commit `c0ac53b7578b74dca8a10d12855f068499d82f0e`; included in release `v1.8` (version `1.8`) |
| `open` | [pydantic/pydantic#11151](https://github.com/pydantic/pydantic/issues/11151) | No closing PR is evidenced; [PR #3552](https://github.com/pydantic/pydantic/pull/3552) refers to python/mypy#11151, not this issue |
| `duplicate` | [pydantic/pydantic#13739](https://github.com/pydantic/pydantic/issues/13739) | GitHub marks it closed with `state_reason=duplicate`; no fixing PR is asserted |
| `unknown` | [pydantic/pydantic#10289](https://github.com/pydantic/pydantic/issues/10289) | Closed as not planned; no Pydantic fixing PR is evidenced |

For #2142, GitHub's issue response links PR #2143 as the closing pull request;
the merged PR says `closes #2142` and identifies the merge commit. The official
v1.8 release is dated 2021-02-26. GitHub's commit comparison from the merge
commit to `v1.8` reports `ahead_by=85`, `behind_by=0`, with the merge commit as
the merge base, verifying that this release contains the fix.

Sources:

- [Issue #2142](https://github.com/pydantic/pydantic/issues/2142)
- [PR #2143](https://github.com/pydantic/pydantic/pull/2143)
- [Merge commit](https://github.com/pydantic/pydantic/commit/c0ac53b7578b74dca8a10d12855f068499d82f0e)
- [v1.8 release](https://github.com/pydantic/pydantic/releases/tag/v1.8)
- [Commit-to-v1.8 comparison](https://github.com/pydantic/pydantic/compare/c0ac53b7578b74dca8a10d12855f068499d82f0e...v1.8)

## System measurements

A retrieval-only baseline run completed against all four v1.0.0
cases. Each case completed without execution or tool errors, used one tool call
and one iteration, and was conservatively classified as `unknown`.
The per-case output is retained in
`evaluation/results/baseline-v1.0.0.jsonl`.

| Metric | Baseline result |
|---|---:|
| Accuracy | 0.25 (1/4) |
| Macro-F1 | 0.10 |
| Fixed-claim precision | N/A (no fixed claims) |
| Fixed-case recall | 0.00 (0/1) |
| False-positive fixed rate | 0.00 (0/3 non-fixed cases) |
| PR / merge-commit / release / version accuracy | 0.00 (one applicable case each) |
| Citation URL validity | 1.00 (31/31) |
| Execution success / execution errors | 1.00 / 0.00 (4/4 completed) |
| Tool-error rate / unresolved rate | 0.00 / 1.00 |
| Average tool calls / iterations | 1.00 / 1.00 |
| Average latency | 4.395075 seconds |

This is a single baseline run, not an agentic-versus-baseline comparison. The
agentic real-data run was blocked by the configured Groq model's daily token
limit before the graph reached verification; consequently no agentic metrics
are reported. Run instructions and metric denominators are documented in
[evaluation.md](evaluation.md). The four-case, single-repository sample is too
small for statistical or broad performance claims.
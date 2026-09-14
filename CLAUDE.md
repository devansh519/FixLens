# FixLens — Claude Project Memory

## What this is

FixLens is an Agentic RAG system that verifies—not just retrieves—whether a
GitHub bug was fixed, in which PR, commit, and release.

**Core rule — never violate this:**

> Use the LLM to decide what to do next. Use deterministic code to establish
> facts that can be computed or verified exactly, such as version comparison,
> PR merge status, commit-in-release checks, and citation existence.

If the LLM is about to decide a version comparison or merge status instead of
calling a deterministic tool, stop. That is the anti-pattern this project
exists to avoid.

---

## Current stage

**STAGE: 3 — Cleaning, chunking, embedding, and local index construction**

---

## Completed work

- [x] Repository selected: `pydantic/pydantic`
- [x] Python 3.12 environment created with `uv`
- [x] GitHub authentication configured through `.env`
- [x] GitHub API client created with rate limiting, retries, and caching
- [x] Issues fetched
- [x] Issue comments fetched
- [x] Pull requests fetched
- [x] Releases fetched
- [x] Tags fetched
- [x] Issue → PR mappings generated
- [x] PR → release matching implemented using PR references in release notes
- [x] Metadata Store generated
- [x] Text cleaning implemented
- [x] Chunking implemented
- [x] Embeddings generated for 806 chunks
- [x] Issue/PR local vector index generated
- [x] Release local vector index generated
- [x] Indexing orchestrator created
- [x] Indexing tests passed: **11 tests**

---

## Current artifacts

```text
data/
├── raw/
│   ├── issues/
│   ├── comments/
│   ├── prs/
│   ├── releases/
│   └── tags/
└── processed/
    ├── mappings.jsonl
    ├── version_mappings.jsonl
    ├── chunks.jsonl
    ├── embedded_chunks.jsonl
    ├── issue_pr_index.jsonl
    └── release_index.jsonl

storage/
└── metadata/
    └── issue_pr_version.json
```

---

## Important limitation

The first version-resolution approach attempted to match release
`target_commitish` values with PR merge commits. This failed because GitHub
releases commonly use branch names such as `main`.

The resolver was corrected to match PR numbers mentioned in release names or
release notes.

However, PRs that are not referenced in release notes may remain unmatched.
Downstream components must handle incomplete evidence conservatively and
abstain when the evidence chain cannot be established.

---

## Build order

1. Repository selection, Python environment, GitHub authentication, and config
2. Ingestion: issues, PRs, releases, tags, timelines → cached raw JSON
3. Relationship resolution: Issue → PR → merge commit → release → Metadata Store
4. Cleaning/chunking/embedding → two vector indexes
5. Planner → Router → Retriever → Metadata lookup → Version verifier
6. Citation verifier → Critic/abstention → confidence scoring
7. Naive-RAG baseline → evaluation harness → ablations → write-up

Do not build the agent loop before the Metadata Store is validated.

---

## Architecture

```text
User Query
    ↓
Planner
    ↓
Router
    ├── Issue/PR retrieval
    └── Release/changelog retrieval
            ↓
Metadata Lookup
    ↓
Version Verifier
    ↓
Citation Verifier
    ↓
Critic / Abstention
    ↓
Final answer:
    verdict + issue/PR/release IDs + confidence
```

---

## Project structure

```text
FixLens/
├── README.md
├── CLAUDE.md
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml
│
├── config/
│   ├── config.yaml
│   └── repos.yaml
│
├── data/
│   ├── raw/
│   │   ├── issues/
│   │   ├── comments/
│   │   ├── timelines/
│   │   ├── prs/
│   │   ├── releases/
│   │   └── tags/
│   │
│   ├── processed/
│   │   ├── issues.jsonl
│   │   ├── prs.jsonl
│   │   ├── releases.jsonl
│   │   ├── mappings.jsonl
│   │   ├── version_mappings.jsonl
│   │   ├── chunks.jsonl
│   │   ├── embedded_chunks.jsonl
│   │   ├── issue_pr_index.jsonl
│   │   └── release_index.jsonl
│   │
│   └── eval/
│
├── storage/
│   ├── metadata/
│   │   └── issue_pr_version.json
│   │
│   └── vectorstores/
│       ├── issues_prs/
│       └── releases/
│
├── src/
│   ├── __init__.py
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── github_client.py
│   │   ├── rate_limiter.py
│   │   ├── cache.py
│   │   ├── fetch_issues.py
│   │   ├── fetch_comments.py
│   │   ├── fetch_prs.py
│   │   ├── fetch_releases.py
│   │   ├── fetch_tags.py
│   │   ├── resolve_links.py
│   │   ├── resolve_versions.py
│   │   ├── build_metadata.py
│   │   └── run_ingestion.py
│   │
│   ├── indexing/
│   │   ├── __init__.py
│   │   ├── cleaners.py
│   │   ├── chunker.py
│   │   ├── embeddings.py
│   │   ├── build_issue_index.py
│   │   ├── build_release_index.py
│   │   └── run_indexing.py
│   │
│   ├── retrieval/
│   │   ├── issue_retriever.py
│   │   └── release_retriever.py
│   │
│   ├── agents/
│   │   ├── planner.py
│   │   └── critic.py
│   │
│   ├── tools/
│   │   ├── metadata_lookup.py
│   │   ├── version_verifier.py
│   │   └── citation_verifier.py
│   │
│   ├── pipeline/
│   │   ├── state.py
│   │   └── graph.py
│   │
│   ├── baseline/
│   │   └── naive_rag.py
│   │
│   └── api/
│       └── main.py
│
├── tests/
│   ├── test_indexing.py
│   └── test_indexing_integration.py
│
├── evaluation/
│   ├── generate_eval_set.py
│   ├── run_eval.py
│   ├── metrics.py
│   ├── compare_baseline.py
│   └── results/
│
├── experiments/
│   ├── baseline/
│   ├── split_indexes/
│   ├── cross_reference/
│   ├── version_verifier/
│   └── critic/
│
├── notebooks/
│   ├── explore_github_data.ipynb
│   ├── inspect_links.ipynb
│   └── analyze_results.ipynb
│
└── docs/
    ├── architecture.md
    ├── data_model.md
    ├── evaluation.md
    └── results.md
```

---

## Coding rules

- Never commit `.env`, tokens, or API keys.
- Keep `.env.example` secret-free.
- All GitHub API access must go through the cached client.
- Use rate limiting, retries, and backoff for GitHub API calls.
- Every metadata record must contain an `evidence` block.
- Never claim that a bug is fixed when the evidence chain is incomplete.
- If evidence is incomplete or contradictory, abstain.
- New deterministic logic must have unit tests before integration.
- Run modules from the project root using:

```powershell
uv run python -m <module>
```

- Prefer stage-level pytest files instead of one test file per module.

---

## Definition of done

- [x] One repository ingested and cached
- [ ] Issue → PR → commit → release manually validated on approximately 10 cases
- [x] Metadata Store generated
- [x] Two local vector indexes built
- [ ] Planner routes at least 3 query types
- [ ] Semver verification is deterministic and tested
- [ ] Citation verification is deterministic and tested
- [ ] Critic can abstain
- [ ] Naive RAG baseline exists
- [ ] Evaluation run recorded:
  - latency
  - cost
  - accuracy
  - false-fix rate

---

## Next stage

**STAGE 4 — Qdrant vector database integration**

Planned steps:

1. Start Qdrant using Docker.
2. Create a Qdrant client wrapper.
3. Create the following collections:
   - `issues_prs`
   - `releases`
4. Upload both local JSONL indexes.
5. Add integration tests for collection creation and vector upload.

Do not build the planner/router agent loop until the Metadata Store and vector
database integration are validated.
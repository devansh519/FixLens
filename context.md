# FixLens — Updated Project Memory

## What this is

FixLens is an Agentic RAG system that verifies—not just retrieves—whether a GitHub bug was fixed, in which PR, commit, and release.

## Core rule — never violate this

Use the LLM to decide what to do next. Use deterministic code to establish facts that can be computed or verified exactly, such as version comparison, PR merge status, commit-in-release checks, and citation existence.

If the LLM is about to decide a version comparison or merge status instead of calling a deterministic tool, stop. That is the anti-pattern this project exists to avoid.

## Current Stage

**STAGE: 6 — Agentic RAG pipeline integration and validation**

Stage 3 and Stage 4 implementation work have been completed.

Stage 5 Planner → Router → Verification pipeline was implemented.

Stage 6 now integrates the real Stage 4 deterministic tools into the agentic pipeline and validates the complete wiring.

**Current test status:**

```
83 passed, 1 warning
```

**Command validated:**

```
uv run pytest tests/test_tool_integration.py tests/test_e2e.py -v
```

**Result:**

```
83 passed, 1 warning in 17.53s
```

The remaining warning is a LangGraph `LangChainPendingDeprecationWarning` regarding the future default value of `allowed_objects`. It is not currently causing test failures.

## Completed Work

### Repository and environment

- [x] Repository selected: pydantic/pydantic
- [x] Python 3.12 environment created using uv
- [x] GitHub authentication configured through .env
- [x] Project configuration files created
- [x] Dependency management configured through pyproject.toml and requirements.txt
- [x] langgraph==1.0.2 installed
- [x] groq==0.37.1 installed
- [x] langchain-groq==1.1.0 installed

### GitHub ingestion

- [x] GitHub API client created
- [x] Rate limiting implemented
- [x] Retries and backoff implemented
- [x] Caching implemented
- [x] Issues fetched
- [x] Issue comments fetched
- [x] Pull requests fetched
- [x] Releases fetched
- [x] Tags fetched
- [x] Issue → PR mappings generated
- [x] PR → release matching implemented using PR references in release names or release notes
- [x] Metadata Store generated

### Cleaning, chunking, and embeddings

- [x] Text cleaning implemented
- [x] Chunking implemented
- [x] Embeddings generated for 806 chunks
- [x] Issue/PR local vector index generated
- [x] Release local vector index generated
- [x] Indexing orchestrator created
- [x] Indexing tests passed: 11 tests

### Qdrant integration

- [x] Qdrant client wrapper created
- [x] Qdrant collection creation implemented
- [x] issues_prs collection configured
- [x] releases collection configured
- [x] Local issue/PR vectors uploaded to Qdrant
- [x] Local release vectors uploaded to Qdrant
- [x] Qdrant retrieval implemented using `query_points`
- [x] Qdrant integration tests created
- [x] Qdrant collection and retrieval behavior tested

**Important implementation note:**

Qdrant's current query interface uses `query_points`. Do not replace it with the removed or outdated `.search()` interface without verifying the installed Qdrant client version.

### Retrieval and deterministic tools

- [x] Issue/PR retrieval wrapper created
- [x] Release retrieval wrapper created
- [x] Metadata lookup tool created
- [x] Metadata lookup supports the current nested metadata structure
- [x] Metadata lookup supports JSON arrays and compatible JSON formats
- [x] Semantic version parsing implemented
- [x] Version comparison implemented
- [x] Minimum-version verification implemented
- [x] Inclusive version-range verification implemented
- [x] Invalid-version handling implemented
- [x] Citation verification implementation created

### Verified Stage 4 retrieval contract

`IssueRetriever.retrieve()` receives an embedded query vector, not the raw query string.

```
raw query
   ↓
QueryEmbedder.embed_query()
   ↓
query_vector
   ↓
IssueRetriever.retrieve()
   ↓
Qdrant
```

`ReleaseRetriever` follows the same pattern.

## Stage 5 — Agentic Pipeline

Implemented:

- [x] Planner
- [x] Router
- [x] Pipeline state
- [x] LangGraph orchestration
- [x] Critic
- [x] Deterministic verification pipeline
- [x] API integration
- [x] Planner tests
- [x] Router tests
- [x] Verifier tests
- [x] Pipeline tests

The architectural principle remains:

- LLM → decides what action/tool to call
- Deterministic tools → establish facts

## Stage 6 — Real Tool Integration

Implemented:

- [x] Real Stage 4 tools connected to pipeline
- [x] FixLensToolRegistry
- [x] Dependency injection for Stage 4 components
- [x] Real metadata lookup adapters
- [x] Real issue retrieval adapter
- [x] Real release retrieval adapter
- [x] Real version verification adapter
- [x] Real citation verification adapter
- [x] Tool registry completeness checking
- [x] Router integration
- [x] Stage 6 integration tests
- [x] Stage 6 E2E pipeline-shape test

**Current registered actions:**

- `lookup_issue`
- `lookup_pr`
- `lookup_commit`
- `lookup_release`
- `retrieve_issue`
- `retrieve_release`
- `verify_version`
- `verify_citations`

### Important Stage 6 implementation details

#### Tool Registry

Current registry supports dependency injection:

- `metadata_lookup`
- `issue_retriever`
- `release_retriever`
- `version_verifier`
- `citation_verifier`
- `embedder`

This allows tests to use fake components without constructing Qdrant or downloading embedding models.

The registry also exposes:

- `available_actions()`
- `missing_actions()`
- `is_complete()`
- `build_router()`

#### Semantic retrieval

Current production flow:

```
retrieve_issue(query)
        ↓
QueryEmbedder.embed_query(query)
        ↓
IssueRetriever.retrieve(vector)
        ↓
Qdrant issues_prs collection
```

and:

```
retrieve_release(query)
        ↓
QueryEmbedder.embed_query(query)
        ↓
ReleaseRetriever.retrieve(vector)
        ↓
Qdrant releases collection
```

This was explicitly validated during Stage 6 integration testing.

#### Version verification

The registry exposes:

```python
verify_version(
    actual_version,
    required_version,
    operation="at_least"
)
```

Supported operations:

- `at_least`
- `compare`

The actual comparison is delegated to the deterministic `VersionVerifier`.

The LLM does not perform the semantic-version comparison itself.

## Current Test Status

Latest validated result:

```
83 passed, 1 warning in 17.53s
```

Specifically:

- `tests/test_tool_integration.py`
- `tests/test_e2e.py`

Both Stage 6 integration tests and the E2E pipeline-shape test are passing.

The complete repository test suite previously reached:

```
83 passed
```

The current LangGraph warning does not indicate a functional failure.

## Current Project Structure

Current workspace structure (571 project files checked; `.git`, `.venv`, `.pytest_cache`, and `__pycache__` generated artifacts are omitted). The `BLANK` tag means the file exists and is zero bytes. Repeated raw-data filenames are shown as patterns with exact file counts.

```
FixLens/
├── .env
├── .env.example
├── .gitignore
├── CLAUDE.md
├── docker-compose.yml
├── pyproject.toml
├── README.md
├── requirements.txt                         [BLANK]
├── uv.lock
├── config/
│   ├── config.yaml
│   └── repos.yaml
├── data/
│   ├── eval/
│   │   ├── duplicate.jsonl                  [BLANK]
│   │   ├── eval_dataset.jsonl               [BLANK]
│   │   ├── fixed.jsonl                      [BLANK]
│   │   └── open.jsonl                       [BLANK]
│   ├── processed/
│   │   ├── chunks.jsonl
│   │   ├── embedded_chunks.jsonl
│   │   ├── issue_pr_index.jsonl
│   │   ├── issues.jsonl                     [BLANK]
│   │   ├── mappings.jsonl
│   │   ├── prs.jsonl                        [BLANK]
│   │   ├── release_index.jsonl
│   │   ├── releases.jsonl                   [BLANK]
│   │   └── version_mappings.jsonl
│   ├── raw/
│   │   ├── cache/                            (empty)
│   │   ├── comments/
│   │   │   └── issue_<number>.json           (407 files)
│   │   ├── issues/
│   │   │   └── page_<number>.json            (10 files)
│   │   ├── prs/
│   │   │   └── page_<number>.json            (56 files)
│   │   ├── releases/
│   │   │   └── page_<number>.json            (2 files)
│   │   ├── tags/
│   │   │   └── page_<number>.json            (3 files)
│   │   └── timelines/                        (empty)
├── docs/
│   ├── architecture.md                       [BLANK]
│   ├── data_model.md                         [BLANK]
│   ├── evaluation.md                         [BLANK]
│   ├── fixlens_architecture.png
│   └── results.md                            [BLANK]
├── evaluation/
│   ├── compare_baseline.py                   [BLANK]
│   ├── generate_eval_set.py                  [BLANK]
│   ├── metrics.py                            [BLANK]
│   ├── results/                              (empty)
│   └── run_eval.py                           [BLANK]
├── experiments/
│   ├── baseline/                             (empty)
│   ├── cross_reference/                      (empty)
│   ├── critic/                               (empty)
│   ├── split_indexes/                        (empty)
│   └── version_verifier/                     (empty)
├── notebooks/
│   ├── analyze_results.ipynb                 [BLANK]
│   ├── explore_github_data.ipynb              [BLANK]
│   └── inspect_links.ipynb                   [BLANK]
├── src/
│   ├── __init__.py                           [BLANK]
│   ├── agents/
│   │   ├── __init__.py                       [BLANK]
│   │   ├── critic.py
│   │   └── planner.py
│   ├── api/
│   │   ├── __init__.py                       [BLANK]
│   │   └── main.py
│   ├── baseline/
│   │   ├── __init__.py                       [BLANK]
│   │   └── naive_rag.py                      [BLANK]
│   ├── embeddings/
│   │   ├── __init__.py                       [BLANK]
│   │   └── embedder.py
│   ├── indexing/
│   │   ├── __init__.py                       [BLANK]
│   │   ├── build_issue_index.py
│   │   ├── build_release_index.py
│   │   ├── chunker.py
│   │   ├── cleaners.py
│   │   ├── embeddings.py
│   │   └── run_indexing.py
│   ├── ingestion/
│   │   ├── __init__.py                       [BLANK]
│   │   ├── build_metadata.py
│   │   ├── cache.py
│   │   ├── fetch_comments.py
│   │   ├── fetch_issues.py
│   │   ├── fetch_prs.py
│   │   ├── fetch_releases.py
│   │   ├── fetch_tags.py
│   │   ├── github_client.py
│   │   ├── rate_limiter.py
│   │   ├── resolve_links.py
│   │   ├── resolve_versions.py
│   │   └── run_ingestion.py
│   ├── pipeline/
│   │   ├── __init__.py                       [BLANK]
│   │   ├── graph.py
│   │   ├── router.py
│   │   ├── state.py
│   │   └── tool_registry.py
│   ├── retrieval/
│   │   ├── __init__.py                       [BLANK]
│   │   ├── issue_retriever.py
│   │   └── release_retriever.py
│   ├── tools/
│   │   ├── __init__.py                       [BLANK]
│   │   ├── citation_verifier.py
│   │   ├── metadata_lookup.py
│   │   └── version_verifier.py
│   ├── vectorstore/
│   │   ├── __init__.py                       [BLANK]
│   │   ├── index_qdrant.py
│   │   └── qdrant_client.py
│   ├── verification/
│   │   └── verifier.py
├── storage/
│   ├── metadata/
│   │   └── issue_pr_version.json
│   └── vectorstores/
│       ├── issues_prs/                       (empty)
│       └── releases/                         (empty)
└── tests/
      ├── test_e2e.py
      ├── test_indexing.py
      ├── test_indexing_integration.py
      ├── test_pipeline.py
      ├── test_planner.py
      ├── test_router.py
      ├── test_tool_integration.py
      ├── test_tools.py
      ├── test_vectorstore.py
      └── test_verifier.py
```

Empty directories are marked `(empty)`. Re-scan the workspace before relying on this snapshot after files or generated data change.

## Next Major Objective

The next stage should move beyond pipeline wiring validation toward real FixLens execution validation.

**Target:**

```
Real User Query
      ↓
Planner
      ↓
Router
      ↓
Real Stage 4 Tools
      ↓
Qdrant + Metadata
      ↓
Evidence collection
      ↓
Critic
      ↓
Deterministic Verification
      ↓
Final FixLens Answer
```

The immediate goal should be to execute a real query against the actual pydantic/pydantic data and verify that FixLens can produce an evidence-backed answer for:

**Was this GitHub issue fixed?**

If yes:
- Which PR?
- Which merge commit?
- Which release/version?
- What evidence proves each step?

Do not mark Stage 6 complete solely because the tests pass. The 83 tests currently establish that the components are correctly wired; a real-data end-to-end query is the next validation checkpoint.


## Latest Checkpoint — 2026-10-01

### Stage 6 real-data validation status

The project is currently paused after reaching the next real E2E blocker.

Latest validation:
- `tests/test_planner.py` — passing
- `tests/test_router.py` — passing
- `tests/test_tool_integration.py` — passing
- Combined result: **10 passed in 58.58s**
- Real test: `tests/test_real_e2e.py::test_real_pydantic_issue_e2e` — currently failing in the Critic
- The previous Groq 413 token-size blocker was addressed successfully; the current failure is a Critic output-schema mismatch.

### Current Critic blocker

The Critic's `CriticDecision` model is currently expecting:

```python
suggested_actions: list[str]
```

but the LLM is returning structured objects:

```python
{
    "action": "lookup_issue",
    "parameters": {
        "issue_number": 11151
    }
}
```

This causes Pydantic validation errors for the returned suggested actions.

Required schema direction:

```python
class SuggestedAction(BaseModel):
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)

class CriticDecision(BaseModel):
    status: Literal["sufficient", "insufficient"]
    reason: str = Field(min_length=1)
    missing_evidence: list[str] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
```

The Critic should also reject or avoid placeholder parameters such as:
- `<MERGE_COMMIT_SHA>`
- `<PR_NUMBER>`
- other invented IDs, SHAs, or release tags.

The LLM must propose actions, but deterministic tools must establish factual IDs and relationships.

### Real E2E observations

The real Pydantic issue query is:

```text
Was pydantic/pydantic issue #11151 fixed?
If it was fixed, identify the PR, merge commit, release/version,
and the evidence supporting each step.
```

A direct deterministic `lookup_issue(11151)` call succeeds, but its returned linked PR #3552 appears suspicious and should **not** automatically be treated as the fixing PR without stronger evidence. PR #3552 is a mypy dependency bump and may represent a metadata/linkage artifact.

Also, `version_info` was returned as `None`, so the release/version is not yet established. The system must discover and verify the release rather than infer or fabricate it.

### Current architectural checkpoint

The important architecture remains:

```text
LLM → chooses next action
        ↓
Deterministic tools → establish facts
        ↓
Evidence
        ↓
Critic
        ↓
Deterministic Verification
        ↓
Final answer
```

Do not mark Stage 6 complete merely because the component tests pass. Real-data correctness still needs validation.

### Git checkpoint

The current work was intended to be committed/tagged as:

```text
Commit: fix: stabilize agent planning and critic pipeline
Tag:    v0.6.0-stage6
```

Recommended commands:

```powershell
git status
git add .
git commit -m "fix: stabilize agent planning and critic pipeline"
git tag -a v0.6.0-stage6 -m "Stage 6 E2E validation checkpoint"
git push origin main
git push origin v0.6.0-stage6
```

When development resumes, continue from the **Critic structured-output/schema fix**, then re-run the real Pydantic E2E test. After that, validate the issue → fixing PR → merge commit → release/version chain for correctness, not merely pipeline completion.

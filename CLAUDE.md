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

The implemented structure now additionally contains Stage 5/6 components:

```
FixLens/

├── CLAUDE.md
├── README.md
├── .env
├── .env.example
├── .gitignore
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
│
├── config/
│   ├── config.yaml
│   └── repos.yaml
│
├── data/
│   ├── raw/
│   │   ├── issues/
│   │   ├── comments/
│   │   ├── prs/
│   │   ├── releases/
│   │   └── tags/
│   │
│   ├── processed/
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
│
├── src/
│   ├── agents/
│   │   ├── planner.py
│   │   └── critic.py
│   │
│   ├── api/
│   │   └── main.py
│   │
│   ├── embeddings/
│   │   ├── __init__.py
│   │   └── embedder.py
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── router.py
│   │   ├── graph.py
│   │   └── tool_registry.py
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── issue_retriever.py
│   │   └── release_retriever.py
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── metadata_lookup.py
│   │   ├── version_verifier.py
│   │   └── citation_verifier.py
│   │
│   ├── verification/
│   │   └── verifier.py
│   │
│   └── vectorstore/
│       ├── __init__.py
│       ├── qdrant_client.py
│       └── index_qdrant.py
│
└── tests/
    ├── test_vectorstore.py
    ├── test_tools.py
    ├── test_planner.py
    ├── test_router.py
    ├── test_verifier.py
    ├── test_pipeline.py
    ├── test_tool_integration.py
    └── test_e2e.py
```

**Note:** The actual repository should still be inspected before making further structural changes rather than assuming every listed file is present exactly as shown.

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
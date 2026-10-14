# FixLens Architecture

## Components

- **FastAPI service** (`src/api/main.py`) accepts a natural-language query and
  invokes the pipeline graph.
- **Planner** chooses investigation actions. Its output is a structured list
  of action/parameter objects, not factual evidence.
- **Tool registry and router** expose deterministic GitHub and retrieval
  operations and record each success or failure as an observation.
- **Critic** evaluates the accumulated observations and requests further
  investigation only while progress is possible.
- **Verifier** applies deterministic rules to the evidence. It does not use
  the Planner or Critic to establish facts.
- **Qdrant retrieval** provides issue/PR and release context; GitHub tools
  supply authoritative records for verification.

## Query flow

```text
query
  -> planner
  -> router (execute non-repeated actions)
  -> sync successful observations into evidence
  -> critic
       -> planner, while progress is possible and budget remains
       -> verifier, when sufficient or no further progress is possible
  -> answer
```

The graph has a configurable iteration budget. An unchanged action is not
executed again, no-progress conditions go to verification, and reaching the
budget also goes to verification. An insufficient Critic decision with no
suggested actions also goes directly to verification. This keeps the loop
finite without treating missing information as proof that a fix does not
exist.

## Evidence and claim boundaries

The state keeps tool observations separate from successful evidence. Failed
observations remain available as errors but are never promoted to evidence.
The verifier checks the chain:

1. The issue belongs to the requested repository.
2. A PR is linked to that issue in the same repository.
3. The PR is merged and has a verified merge commit.
4. Release and version claims are independently supported by release/tag
   evidence.

`FIXED` requires the first three conditions. It does not imply that release
information was found. Missing links, commits, or releases stay unknown and
are not filled in by the language model. API responses return the verifier's
status and reason alongside the answer.

## Ingestion and retrieval

`config/repos.yaml` selects the repository for ingestion. The ingestion
pipeline stores raw GitHub pages under `data/raw/`, resolves issue-to-PR links
and versions under `data/processed/`, then writes normalized metadata under
`storage/metadata/`. Link extraction scopes issue numbers to the repository,
so a reference to `python/mypy#11151` cannot be joined to
`pydantic/pydantic#11151`.

The indexing pipeline chunks and embeds issue, PR, and release content. It
builds separate issue/PR and release indexes and loads vectors into Qdrant.
Raw, processed, metadata, and vector-store artifacts are generated locally;
they are not source-controlled.
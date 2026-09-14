# FixLens

**Look beyond the issue. Verify the fix.**

FixLens is an agentic RAG system that answers evidence-backed questions
about GitHub bug fixes.

It reasons over:

- GitHub Issues
- Pull Requests
- Commits
- Releases
- Version tags

## Development Setup

This project uses `uv` for Python environment and dependency management.

```powershell
uv venv
.\.venv\Scripts\Activate.ps1
uv sync
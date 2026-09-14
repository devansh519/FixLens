
import json
from pathlib import Path

import yaml

from src.ingestion.github_client import GitHubClient


CONFIG_PATH = Path("config/repos.yaml")
OUTPUT_DIR = Path("data/raw/issues")


def load_repository() -> tuple[str, str]:
    """Load the enabled repository from repos.yaml."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing configuration: {CONFIG_PATH}")

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    repositories = config.get("repositories", [])

    for repository in repositories:
        if repository.get("enabled", False):
            owner = repository.get("owner")
            name = repository.get("name")

            if owner and name:
                return owner, name

    raise RuntimeError("No enabled repository found in config/repos.yaml")


def save_json(data: list[dict], page: int) -> None:
    """Save one page of issues."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / f"page_{page}.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

    print(f"[SAVED] {output_path} ({len(data)} issues)")


def fetch_issues(
    github: GitHubClient,
    owner: str,
    repo: str,
    per_page: int = 100,
) -> int:
    """Fetch repository issues while excluding pull requests."""

    page = 1
    total_issues = 0

    while True:
        print(f"[FETCH] Issues page {page}")

        response = github.get(
            "/search/issues",
            params={
                "q": f"repo:{owner}/{repo} is:issue",
                "per_page": per_page,
                "page": page,
            },
            use_cache=False,
        )

        issues = response.get("items", [])

        if not issues:
            break

        save_json(issues, page)
        total_issues += len(issues)

        if len(issues) < per_page:
            break

        page += 1

    return total_issues


def main() -> None:
    owner, repo = load_repository()

    print(f"Repository selected: {owner}/{repo}")

    github = GitHubClient()

    try:
        total = fetch_issues(github, owner, repo)
        print(f"\nCompleted. Total issues fetched: {total}")

    finally:
        github.close()


if __name__ == "__main__":
    main()
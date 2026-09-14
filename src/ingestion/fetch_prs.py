
import json
from pathlib import Path

import yaml

from src.ingestion.github_client import GitHubClient


CONFIG_PATH = Path("config/repos.yaml")
OUTPUT_DIR = Path("data/raw/prs")


def load_repository() -> tuple[str, str]:
    """Load the enabled repository from repos.yaml."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing configuration: {CONFIG_PATH}")

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    for repository in config.get("repositories", []):
        if repository.get("enabled", False):
            owner = repository.get("owner")
            name = repository.get("name")

            if owner and name:
                return owner, name

    raise RuntimeError("No enabled repository found in config/repos.yaml")


def save_json(data: list[dict], page: int) -> None:
    """Save one page of pull requests."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / f"page_{page}.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

    print(f"[SAVED] {output_path} ({len(data)} PRs)")


def fetch_prs(
    github: GitHubClient,
    owner: str,
    repo: str,
    per_page: int = 100,
) -> int:
    """Fetch all pull requests, including open and closed PRs."""

    page = 1
    total_prs = 0

    while True:
        print(f"[FETCH] Pull requests page {page}")

        response = github.get(
            f"/repos/{owner}/{repo}/pulls",
            params={
                "state": "all",
                "sort": "created",
                "direction": "asc",
                "per_page": per_page,
                "page": page,
            },
            use_cache=False,
        )

        prs = response if isinstance(response, list) else []

        if not prs:
            break

        save_json(prs, page)
        total_prs += len(prs)

        if len(prs) < per_page:
            break

        page += 1

    return total_prs


def main() -> None:
    owner, repo = load_repository()

    print(f"Repository selected: {owner}/{repo}")

    github = GitHubClient()

    try:
        total = fetch_prs(github, owner, repo)
        print(f"\nCompleted. Total PRs fetched: {total}")

    finally:
        github.close()


if __name__ == "__main__":
    main()
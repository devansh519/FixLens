import json
from pathlib import Path

import yaml

from src.ingestion.github_client import GitHubClient


CONFIG_PATH = Path("config/repos.yaml")
OUTPUT_DIR = Path("data/raw/tags")


def load_repository() -> tuple[str, str]:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    for repository in config.get("repositories", []):
        if repository.get("enabled", False):
            return repository["owner"], repository["name"]

    raise RuntimeError("No enabled repository found in config/repos.yaml")


def fetch_tags(
    github: GitHubClient,
    owner: str,
    repo: str,
    per_page: int = 100,
) -> int:
    page = 1
    total_tags = 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        print(f"[FETCH] Tags page {page}")

        response = github.get(
            f"/repos/{owner}/{repo}/tags",
            params={
                "per_page": per_page,
                "page": page,
            },
            use_cache=False,
        )

        tags = response if isinstance(response, list) else []

        if not tags:
            break

        output_path = OUTPUT_DIR / f"page_{page}.json"

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(tags, file, indent=2)

        print(f"[SAVED] {output_path} ({len(tags)} tags)")

        total_tags += len(tags)

        if len(tags) < per_page:
            break

        page += 1

    return total_tags


def main() -> None:
    owner, repo = load_repository()
    print(f"Repository selected: {owner}/{repo}")

    github = GitHubClient()

    try:
        total = fetch_tags(github, owner, repo)
        print(f"\nCompleted. Total tags fetched: {total}")
    finally:
        github.close()


if __name__ == "__main__":
    main()
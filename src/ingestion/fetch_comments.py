import json
from pathlib import Path

import yaml

from src.ingestion.github_client import GitHubClient


CONFIG_PATH = Path("config/repos.yaml")
ISSUES_DIR = Path("data/raw/issues")
COMMENTS_DIR = Path("data/raw/comments")


def load_repository() -> tuple[str, str]:
    """Load the enabled repository from repos.yaml."""
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    for repository in config.get("repositories", []):
        if repository.get("enabled", False):
            owner = repository.get("owner")
            name = repository.get("name")

            if owner and name:
                return owner, name

    raise RuntimeError("No enabled repository found in config/repos.yaml")


def load_issues() -> list[dict]:
    """Load issues from all saved JSON pages."""
    issues = []

    for page_file in sorted(ISSUES_DIR.glob("page_*.json")):
        with page_file.open("r", encoding="utf-8") as file:
            page_issues = json.load(file)

        issues.extend(page_issues)

    return issues


def save_comments(issue_number: int, comments: list[dict]) -> None:
    """Save comments for one issue."""
    COMMENTS_DIR.mkdir(parents=True, exist_ok=True)

    output_path = COMMENTS_DIR / f"issue_{issue_number}.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(comments, file, indent=2)

    print(f"[SAVED] {output_path} ({len(comments)} comments)")


def fetch_comments(
    github: GitHubClient,
    owner: str,
    repo: str,
    issues: list[dict],
) -> int:
    """Fetch comments for every issue."""
    total_comments = 0

    for index, issue in enumerate(issues, start=1):
        issue_number = issue["number"]

        print(
            f"[FETCH] Issue {issue_number} "
            f"({index}/{len(issues)})"
        )

        response = github.get(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            params={
                "per_page": 100,
                "page": 1,
            },
            use_cache=False,
        )

        comments = response if isinstance(response, list) else []

        save_comments(issue_number, comments)
        total_comments += len(comments)

    return total_comments


def main() -> None:
    owner, repo = load_repository()
    issues = load_issues()

    print(f"Repository selected: {owner}/{repo}")
    print(f"Issues loaded: {len(issues)}")

    github = GitHubClient()

    try:
        total = fetch_comments(github, owner, repo, issues)
        print(f"\nCompleted. Total comments fetched: {total}")

    finally:
        github.close()


if __name__ == "__main__":
    main()
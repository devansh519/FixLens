import json
import re
from pathlib import Path

from src.ingestion.resolve_links import repository_from_url

MAPPINGS_PATH = Path("data/processed/mappings.jsonl")
RELEASES_DIR = Path("data/raw/releases")
OUTPUT_PATH = Path("data/processed/version_mappings.jsonl")


PR_PATTERN = re.compile(
    r"(?<![\w/])#(\d+)\b",
    re.IGNORECASE,
)
PR_URL_PATTERN = re.compile(
    r"https?://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)"
    r"/pull/(?P<number>\d+)\b",
    re.IGNORECASE,
)
QUALIFIED_PR_REFERENCE_PATTERN = re.compile(
    r"(?<![\w/])(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)#(?P<number>\d+)\b"
)


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def load_releases() -> list[dict]:
    releases = []

    for path in sorted(RELEASES_DIR.glob("page_*.json")):
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            releases.extend(data)

    return releases


def extract_pr_numbers(release: dict) -> set[int]:
    text = "\n".join(
        [
            release.get("name") or "",
            release.get("body") or "",
        ]
    )

    repository = repository_from_url(release.get("html_url"))
    if repository is None:
        return set()

    numbers = {
        int(match.group("number"))
        for match in PR_URL_PATTERN.finditer(text)
        if (
            match.group("owner").casefold(),
            match.group("repo").casefold(),
        ) == repository
    }

    def collect_qualified(match: re.Match[str]) -> str:
        linked_repository = (
            match.group("owner").casefold(),
            match.group("repo").casefold(),
        )
        if linked_repository == repository:
            numbers.add(int(match.group("number")))
        return " "

    text = PR_URL_PATTERN.sub(" ", text)
    text = QUALIFIED_PR_REFERENCE_PATTERN.sub(collect_qualified, text)
    numbers.update(int(number) for number in PR_PATTERN.findall(text))
    return numbers


def resolve_release_mappings(
    mappings: list[dict],
    releases: list[dict],
) -> list[dict]:
    """Join release PR references by repository and PR number."""
    release_by_pr: dict[tuple[tuple[str, str], int], dict] = {}
    for release in releases:
        repository = repository_from_url(release.get("html_url"))
        if repository is None:
            continue
        for pr_number in extract_pr_numbers(release):
            release_by_pr[(repository, pr_number)] = release

    resolved = []
    for mapping in mappings:
        repository = mapping.get("repository")
        if isinstance(repository, str) and "/" in repository:
            owner, repo = repository.split("/", 1)
            repository_key = (owner.casefold(), repo.casefold())
        else:
            repository_key = repository_from_url(mapping.get("pr_url"))
        pr_number = mapping.get("pr_number")
        release = (
            release_by_pr.get((repository_key, pr_number))
            if repository_key is not None and isinstance(pr_number, int)
            else None
        )
        resolved.append({
            **mapping,
            "version_info": {
                "release": release,
                "tag_name": release.get("tag_name") if release else None,
            },
        })
    return resolved


def resolve_versions() -> None:
    mappings = load_jsonl(MAPPINGS_PATH)
    releases = load_releases()
    resolved = resolve_release_mappings(mappings, releases)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        for item in resolved:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")

    matched = sum(
        1
        for item in resolved
        if item["version_info"]["release"] is not None
    )

    print(f"[SAVED] {OUTPUT_PATH}")
    print(f"Total mappings: {len(resolved)}")
    print(f"Matched releases: {matched}")


if __name__ == "__main__":
    resolve_versions()
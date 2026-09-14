import json
import re
from pathlib import Path


MAPPINGS_PATH = Path("data/processed/mappings.jsonl")
RELEASES_DIR = Path("data/raw/releases")
OUTPUT_PATH = Path("data/processed/version_mappings.jsonl")


PR_PATTERN = re.compile(
    r"(?:pull/|#)(\d+)",
    re.IGNORECASE,
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

    return {
        int(match)
        for match in PR_PATTERN.findall(text)
    }


def resolve_versions() -> None:
    mappings = load_jsonl(MAPPINGS_PATH)
    releases = load_releases()

    release_by_pr: dict[int, dict] = {}

    for release in releases:
        for pr_number in extract_pr_numbers(release):
            release_by_pr[pr_number] = release

    resolved = []

    for mapping in mappings:
        pr_number = mapping.get("pr_number")
        release = release_by_pr.get(pr_number)

        version_info = {
            "release": release,
            "tag_name": release.get("tag_name") if release else None,
        }

        resolved_mapping = {
            **mapping,
            "version_info": version_info,
        }

        resolved.append(resolved_mapping)

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
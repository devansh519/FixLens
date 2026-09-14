import json
from pathlib import Path


ISSUES_DIR = Path("data/raw/issues")
COMMENTS_DIR = Path("data/raw/comments")
PRS_DIR = Path("data/raw/prs")
VERSION_MAPPINGS_PATH = Path("data/processed/version_mappings.jsonl")

OUTPUT_PATH = Path("storage/metadata/issue_pr_version.json")


def load_json_pages(directory: Path) -> list[dict]:
    records = []

    for file_path in sorted(directory.glob("page_*.json")):
        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            records.extend(data)

    return records


def load_version_mappings() -> list[dict]:
    if not VERSION_MAPPINGS_PATH.exists():
        return []

    mappings = []

    with VERSION_MAPPINGS_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                mappings.append(json.loads(line))

    return mappings


def load_comments(issue_number: int) -> list[dict]:
    comments_path = COMMENTS_DIR / f"issue_{issue_number}.json"

    if not comments_path.exists():
        return []

    with comments_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return data if isinstance(data, list) else []


def build_metadata() -> int:
    issues = load_json_pages(ISSUES_DIR)
    prs = load_json_pages(PRS_DIR)
    mappings = load_version_mappings()

    issues_by_number = {
        issue["number"]: issue
        for issue in issues
        if "number" in issue
    }

    prs_by_number = {
        pr["number"]: pr
        for pr in prs
        if "number" in pr
    }

    metadata_records = []

    for mapping in mappings:
        issue_number = mapping.get("issue_number")
        pr_number = mapping.get("pr_number")

        issue = issues_by_number.get(issue_number, {})
        pr = prs_by_number.get(pr_number, {})

        record = {
            "issue": {
                "number": issue_number,
                "title": issue.get("title"),
                "body": issue.get("body"),
                "state": issue.get("state"),
                "url": issue.get("html_url"),
                "comments": load_comments(issue_number),
            },
            "pull_request": {
                "number": pr_number,
                "title": pr.get("title"),
                "body": pr.get("body"),
                "state": pr.get("state"),
                "merged_at": pr.get("merged_at"),
                "merge_commit_sha": pr.get("merge_commit_sha"),
                "url": pr.get("html_url"),
            },
            "version_info": mapping.get("version_info", {}),
            "evidence": {
                "issue_url": issue.get("html_url"),
                "pr_url": pr.get("html_url"),
                "merge_commit_sha": pr.get("merge_commit_sha"),
            },
        }

        metadata_records.append(record)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(metadata_records, file, indent=2)

    print(f"[SAVED] {OUTPUT_PATH}")
    print(f"Metadata records created: {len(metadata_records)}")

    return len(metadata_records)


def main() -> None:
    build_metadata()


if __name__ == "__main__":
    main()
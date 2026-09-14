import json
import re
from pathlib import Path


ISSUES_DIR = Path("data/raw/issues")
PRS_DIR = Path("data/raw/prs")
OUTPUT_PATH = Path("data/processed/mappings.jsonl")


ISSUE_REFERENCE_PATTERN = re.compile(r"(?<!\w)#(\d+)")


def load_json_pages(directory: Path) -> list[dict]:
    records = []

    for file_path in sorted(directory.glob("page_*.json")):
        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            records.extend(data)

    return records


def extract_issue_numbers(text: str) -> set[int]:
    if not text:
        return set()

    return {
        int(number)
        for number in ISSUE_REFERENCE_PATTERN.findall(text)
    }


def resolve_links() -> int:
    issues = load_json_pages(ISSUES_DIR)
    prs = load_json_pages(PRS_DIR)

    issue_numbers = {
        issue["number"]
        for issue in issues
        if "number" in issue
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    mapping_count = 0

    with OUTPUT_PATH.open("w", encoding="utf-8") as output_file:
        for pr in prs:
            pr_number = pr.get("number")
            title = pr.get("title", "")
            body = pr.get("body") or ""

            referenced_issues = extract_issue_numbers(
                f"{title}\n{body}"
            )

            for issue_number in sorted(referenced_issues):
                if issue_number not in issue_numbers:
                    continue

                mapping = {
                    "issue_number": issue_number,
                    "pr_number": pr_number,
                    "pr_state": pr.get("state"),
                    "pr_merged": pr.get("merged_at") is not None,
                    "pr_url": pr.get("html_url"),
                    "merge_commit_sha": pr.get("merge_commit_sha"),
                    "source": "pr_title_or_body_reference",
                }

                output_file.write(
                    json.dumps(mapping) + "\n"
                )

                mapping_count += 1

    print(f"[SAVED] {OUTPUT_PATH}")
    print(f"Mappings created: {mapping_count}")

    return mapping_count


def main() -> None:
    resolve_links()


if __name__ == "__main__":
    main()
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ISSUES_DIR = Path("data/raw/issues")
PRS_DIR = Path("data/raw/prs")
OUTPUT_PATH = Path("data/processed/mappings.jsonl")


ISSUE_REFERENCE_PATTERN = re.compile(r"(?<![\w/])#(\d+)\b")
QUALIFIED_ISSUE_REFERENCE_PATTERN = re.compile(
    r"(?<![\w/])(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)#(?P<number>\d+)\b"
)
HTML_LINK_PATTERN = re.compile(
    r"<a\b[^>]*\bhref=[\"'](?P<url>[^\"']+)[\"'][^>]*>"
    r"(?P<text>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
MARKDOWN_LINK_PATTERN = re.compile(
    r"\[(?P<text>[^\]]*)\]\((?P<url>https?://[^)]+)\)"
)
URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)


def load_json_pages(directory: Path) -> list[dict]:
    records = []

    for file_path in sorted(directory.glob("page_*.json")):
        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            records.extend(data)

    return records


def repository_from_url(url: str | None) -> tuple[str, str] | None:
    if not isinstance(url, str):
        return None
    parsed = urlsplit(url)
    if parsed.hostname not in {"github.com", "api.github.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if parts and parts[0] == "repos":
        parts = parts[1:]
    if len(parts) < 2:
        return None
    return parts[0].casefold(), parts[1].casefold()


def _issue_number_from_url(url: str) -> int | None:
    parsed = urlsplit(url)
    if parsed.hostname not in {"github.com", "api.github.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if parts and parts[0] == "repos":
        parts = parts[1:]
    for index, part in enumerate(parts[:-1]):
        if part == "issues" and parts[index + 1].isdigit():
            return int(parts[index + 1])
    return None


def extract_issue_numbers(
    text: str,
    repository: tuple[str, str] | None = None,
) -> set[int]:
    if not text:
        return set()

    referenced: set[int] = set()

    def same_repository_link(match: re.Match[str]) -> str:
        linked_repository = repository_from_url(match.group("url"))
        if repository and linked_repository == repository:
            linked_issue = _issue_number_from_url(match.group("url"))
            if linked_issue is not None:
                referenced.add(linked_issue)
            referenced.update(
                int(number)
                for number in ISSUE_REFERENCE_PATTERN.findall(match.group("text"))
            )
        return " "

    text = HTML_LINK_PATTERN.sub(same_repository_link, text)
    text = MARKDOWN_LINK_PATTERN.sub(same_repository_link, text)

    def same_repository_qualified_reference(match: re.Match[str]) -> str:
        linked_repository = (
            match.group("owner").casefold(),
            match.group("repo").casefold(),
        )
        if repository and linked_repository == repository:
            referenced.add(int(match.group("number")))
        return " "

    text = QUALIFIED_ISSUE_REFERENCE_PATTERN.sub(
        same_repository_qualified_reference,
        text,
    )

    def same_repository_url(match: re.Match[str]) -> str:
        url = match.group().rstrip(".,;:!?")
        linked_repository = repository_from_url(url)
        if repository and linked_repository == repository:
            linked_issue = _issue_number_from_url(url)
            if linked_issue is not None:
                referenced.add(linked_issue)
        return " "

    text = URL_PATTERN.sub(same_repository_url, text)
    referenced.update(
        int(number)
        for number in ISSUE_REFERENCE_PATTERN.findall(text)
    )
    return referenced


def resolve_link_records(
    issues: list[dict],
    prs: list[dict],
) -> list[dict]:
    issue_numbers_by_repository: dict[tuple[str, str], set[int]] = {}
    for issue in issues:
        repository = repository_from_url(issue.get("html_url"))
        issue_number = issue.get("number")
        if repository and isinstance(issue_number, int):
            issue_numbers_by_repository.setdefault(repository, set()).add(
                issue_number
            )

    mappings = []
    for pr in prs:
        repository = repository_from_url(pr.get("html_url"))
        if not repository:
            continue
        title = pr.get("title", "")
        body = pr.get("body") or ""
        available_issue_numbers = issue_numbers_by_repository.get(repository, set())
        referenced_issues = extract_issue_numbers(
            f"{title}\n{body}",
            repository,
        )
        for issue_number in sorted(referenced_issues & available_issue_numbers):
            mappings.append({
                "repository": "/".join(repository),
                "issue_number": issue_number,
                "pr_number": pr.get("number"),
                "pr_state": pr.get("state"),
                "pr_merged": pr.get("merged_at") is not None,
                "pr_url": pr.get("html_url"),
                "merge_commit_sha": pr.get("merge_commit_sha"),
                "source": "pr_title_or_body_reference",
            })
    return mappings


def resolve_links(
    issues_dir: Path = ISSUES_DIR,
    prs_dir: Path = PRS_DIR,
    output_path: Path = OUTPUT_PATH,
) -> int:
    issues = load_json_pages(issues_dir)
    prs = load_json_pages(prs_dir)
    mappings = resolve_link_records(issues, prs)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as output_file:
        for mapping in mappings:
            output_file.write(json.dumps(mapping) + "\n")

    print(f"[SAVED] {output_path}")
    print(f"Mappings created: {len(mappings)}")

    return len(mappings)


def main() -> None:
    resolve_links()


if __name__ == "__main__":
    main()

import re
from typing import Any


def clean_text(text: str | None) -> str:
    """Clean GitHub text while preserving useful technical content."""
    if not text:
        return ""

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove HTML comments.
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Normalize excessive whitespace while preserving paragraphs.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def clean_record(record: dict[str, Any]) -> dict[str, Any]:
    """Clean text fields in a GitHub record."""
    cleaned = {}

    for key, value in record.items():
        if isinstance(value, str):
            cleaned[key] = clean_text(value)
        elif isinstance(value, list):
            cleaned[key] = [
                clean_record(item) if isinstance(item, dict)
                else clean_text(item) if isinstance(item, str)
                else item
                for item in value
            ]
        elif isinstance(value, dict):
            cleaned[key] = clean_record(value)
        else:
            cleaned[key] = value

    return cleaned


def build_issue_document(issue: dict[str, Any]) -> str:
    """Convert an issue and its comments into searchable text."""
    parts = [
        f"Issue #{issue.get('number', '')}",
        f"Title: {clean_text(issue.get('title'))}",
        f"State: {issue.get('state', '')}",
        f"Body:\n{clean_text(issue.get('body'))}",
    ]

    comments = issue.get("comments", [])

    if comments:
        parts.append("Comments:")

        for comment in comments:
            user = (comment.get("user") or {}).get("login", "unknown")
            body = clean_text(comment.get("body"))

            if body:
                parts.append(f"{user}: {body}")

    return "\n\n".join(part for part in parts if part.strip())


def build_pr_document(pr: dict[str, Any]) -> str:
    """Convert a pull request into searchable text."""
    parts = [
        f"Pull Request #{pr.get('number', '')}",
        f"Title: {clean_text(pr.get('title'))}",
        f"State: {pr.get('state', '')}",
        f"Body:\n{clean_text(pr.get('body'))}",
        f"Merged at: {pr.get('merged_at', '')}",
        f"Merge commit: {pr.get('merge_commit_sha', '')}",
    ]

    return "\n\n".join(part for part in parts if part.strip())


def build_release_document(release: dict[str, Any]) -> str:
    """Convert a release into searchable text."""
    parts = [
        f"Release: {release.get('tag_name', '')}",
        f"Name: {clean_text(release.get('name'))}",
        f"Body:\n{clean_text(release.get('body'))}",
        f"Published at: {release.get('published_at', '')}",
        f"Target commit: {release.get('target_commitish', '')}",
    ]

    return "\n\n".join(part for part in parts if part.strip())


if __name__ == "__main__":
    sample = {
        "number": 123,
        "title": "  Example issue  ",
        "body": "Problem description.\n\n\n<!-- hidden comment -->",
    }

    cleaned = clean_record(sample)

    print("Cleaner test:")
    print(cleaned)
    print("\nDocument test:")
    print(build_issue_document(cleaned))

import subprocess
import sys


INGESTION_STEPS = [
    ("Fetching issues", "src.ingestion.fetch_issues"),
    ("Fetching issue comments", "src.ingestion.fetch_comments"),
    ("Fetching pull requests", "src.ingestion.fetch_prs"),
    ("Fetching releases", "src.ingestion.fetch_releases"),
    ("Fetching tags", "src.ingestion.fetch_tags"),
    ("Resolving issue-to-PR links", "src.ingestion.resolve_links"),
    ("Resolving versions", "src.ingestion.resolve_versions"),
    ("Building metadata", "src.ingestion.build_metadata"),
]


def run_step(description: str, module: str) -> None:
    """Run one ingestion module."""
    print(f"\n{'=' * 60}")
    print(description)
    print(f"{'=' * 60}\n")

    subprocess.run(
        [sys.executable, "-m", module],
        check=True,
    )


def main() -> None:
    """Run the complete ingestion pipeline."""
    for description, module in INGESTION_STEPS:
        run_step(description, module)

    print("\nIngestion pipeline completed successfully.")


if __name__ == "__main__":
    main()
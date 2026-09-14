import subprocess
import sys


INDEXING_STEPS = [
    ("Building chunks", "src.indexing.chunker"),
    ("Generating embeddings", "src.indexing.embeddings"),
    ("Building issue/PR index", "src.indexing.build_issue_index"),
    ("Building release index", "src.indexing.build_release_index"),
]


def run_step(description: str, module: str) -> None:
    print(f"\n{'=' * 60}")
    print(description)
    print(f"{'=' * 60}")

    result = subprocess.run(
        [sys.executable, "-m", module],
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Indexing step failed: {module}")


def main() -> None:
    for description, module in INDEXING_STEPS:
        run_step(description, module)

    print("\nIndexing pipeline completed successfully.")


if __name__ == "__main__":
    main()
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

from src.ingestion.cache import ResponseCache
from src.ingestion.rate_limiter import RateLimiter

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    raise RuntimeError("GITHUB_TOKEN is missing from .env")


class GitHubClient:
    """GitHub API client with rate limiting, retries, and caching."""

    def __init__(
        self,
        api_url: str = "https://api.github.com",
        timeout: float = 30.0,
        max_retries: int = 3,
        requests_per_hour: int = 5000,
    ):
        self.max_retries = max_retries

        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        self.client = httpx.Client(
            base_url=api_url,
            headers=self.headers,
            timeout=timeout,
        )

        self.rate_limiter = RateLimiter(requests_per_hour)
        self.cache = ResponseCache()

    def get(
        self,
        endpoint: str,
        params: dict | None = None,
        use_cache: bool = True,
    ) -> Any:
        """Send a GET request to GitHub with caching and retries."""

        cached_data = None

        if use_cache:
            cached_data = self.cache.get(endpoint, params)

            if cached_data is not None:
                print(f"[CACHE] {endpoint}")
                return cached_data

        for attempt in range(1, self.max_retries + 1):
            self.rate_limiter.wait()

            try:
                response = self.client.get(endpoint, params=params)

                if response.status_code == 429:
                    retry_after = int(
                        response.headers.get("Retry-After", "60")
                    )
                    print(
                        f"[WARN] Rate limited. Waiting {retry_after} seconds."
                    )
                    time.sleep(retry_after)
                    continue

                if response.status_code in {500, 502, 503, 504}:
                    raise httpx.HTTPStatusError(
                        "Temporary GitHub server error",
                        request=response.request,
                        response=response,
                    )

                response.raise_for_status()
                data = response.json()

                if use_cache:
                    self.cache.set(endpoint, data, params)

                return data

            except (httpx.RequestError, httpx.HTTPStatusError) as error:
                if attempt == self.max_retries:
                    raise RuntimeError(
                        f"GitHub request failed after {self.max_retries} attempts: "
                        f"{endpoint}"
                    ) from error

                wait_time = 2**attempt

                print(
                    f"[WARN] Request failed on attempt {attempt}. "
                    f"Retrying in {wait_time} seconds..."
                )

                time.sleep(wait_time)

        raise RuntimeError("Unexpected request failure.")

    def get_repository(self, owner: str, repo: str) -> dict:
        """Fetch repository information."""
        return self.get(f"/repos/{owner}/{repo}")

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()


if __name__ == "__main__":
    github = GitHubClient()

    try:
        repository = github.get_repository("encode", "httpx")

        print(f"Connected to: {repository['full_name']}")
        print(f"Private repository: {repository['private']}")

    finally:
        github.close()
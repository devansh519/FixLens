import hashlib
import json
from pathlib import Path
from typing import Any


class ResponseCache:
    """Stores GitHub API responses as local JSON files."""

    def __init__(self, cache_dir: str = "data/raw/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, url: str, params: dict | None = None) -> Path:
        cache_key = json.dumps(
            {
                "url": url,
                "params": params or {},
            },
            sort_keys=True,
        )

        cache_hash = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()

        return self.cache_dir / f"{cache_hash}.json"

    def get(self, url: str, params: dict | None = None) -> Any | None:
        """Return cached data if it exists."""
        cache_path = self._get_cache_path(url, params)

        if not cache_path.exists():
            return None

        with cache_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def set(self, url: str, data: Any, params: dict | None = None) -> None:
        """Save API response data to the cache."""
        cache_path = self._get_cache_path(url, params)

        with cache_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

    def clear(self) -> None:
        """Delete all cached responses."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
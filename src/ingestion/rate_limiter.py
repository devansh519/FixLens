import time
from threading import Lock


class RateLimiter:
    """Simple thread-safe rate limiter for GitHub API requests."""

    def __init__(self, requests_per_hour: int = 5000):
        self.requests_per_hour = requests_per_hour
        self.min_interval = 3600 / requests_per_hour
        self.last_request_time = 0.0
        self.lock = Lock()

    def wait(self) -> None:
        """Wait until the next request is allowed."""
        with self.lock:
            elapsed = time.monotonic() - self.last_request_time
            remaining = self.min_interval - elapsed

            if remaining > 0:
                time.sleep(remaining)

            self.last_request_time = time.monotonic()
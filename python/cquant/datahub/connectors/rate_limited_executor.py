"""Rate-limited parallel executor for data fetching.

Supports:
- Per-connector rate limiting (requests/minute)
- Parallel fetching with ThreadPoolExecutor
- Automatic retry with exponential backoff on rate limit errors
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a connector."""
    requests_per_minute: int = 40
    retry_after_seconds: int = 60
    max_retries: int = 3
    backoff_factor: float = 2.0


class RateLimitedExecutor:
    """Executes tasks with rate limiting and retry logic."""

    def __init__(self, config: RateLimitConfig, max_workers: int = 4):
        self._config = config
        self._max_workers = max_workers
        self._interval = 60.0 / config.requests_per_minute  # seconds between requests
        self._last_request_time = 0.0
        self._request_count = 0
        self._minute_start = time.time()

    def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limit."""
        now = time.time()

        # Reset counter every minute
        if now - self._minute_start >= 60:
            self._request_count = 0
            self._minute_start = now

        # If we've hit the limit, wait until next minute
        if self._request_count >= self._config.requests_per_minute:
            wait_time = 60 - (now - self._minute_start)
            if wait_time > 0:
                logger.info("Rate limit reached (%d/%d), waiting %.1fs",
                           self._request_count, self._config.requests_per_minute, wait_time)
                time.sleep(wait_time)
            self._request_count = 0
            self._minute_start = time.time()

        # Ensure minimum interval between requests
        elapsed = time.time() - self._last_request_time
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)

        self._last_request_time = time.time()
        self._request_count += 1

    def execute_with_retry(self, task: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a single task with retry logic."""
        last_error = None
        for attempt in range(self._config.max_retries + 1):
            try:
                self._wait_for_rate_limit()
                return task(*args, **kwargs)
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check if it's a rate limit error
                if any(keyword in error_str for keyword in ["频率超限", "rate limit", "429", "too many requests"]):
                    wait_time = self._config.retry_after_seconds * (self._config.backoff_factor ** attempt)
                    logger.warning("Rate limit error (attempt %d/%d), waiting %.0fs: %s",
                                  attempt + 1, self._config.max_retries + 1, wait_time, e)
                    time.sleep(wait_time)
                elif attempt < self._config.max_retries:
                    wait_time = 5 * (self._config.backoff_factor ** attempt)
                    logger.warning("Request failed (attempt %d/%d), retrying in %.0fs: %s",
                                  attempt + 1, self._config.max_retries + 1, wait_time, e)
                    time.sleep(wait_time)
                else:
                    raise

        raise last_error  # type: ignore

    def execute_parallel(
        self,
        tasks: list[Callable[..., T]],
        *args: Any,
        **kwargs: Any,
    ) -> list[T | Exception]:
        """Execute multiple tasks in parallel with rate limiting."""
        results: list[T | Exception] = [None] * len(tasks)  # type: ignore

        def run_task(index: int, task: Callable[..., T]) -> tuple[int, T | Exception]:
            try:
                result = self.execute_with_retry(task, *args, **kwargs)
                return (index, result)
            except Exception as e:
                return (index, e)

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = [
                executor.submit(run_task, i, task)
                for i, task in enumerate(tasks)
            ]

            for future in as_completed(futures):
                try:
                    index, result = future.result()
                    results[index] = result
                except Exception as e:
                    logger.error("Unexpected error in parallel execution: %s", e)

        return results

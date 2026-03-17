"""Retry utilities with exponential backoff."""

from __future__ import annotations

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator for retrying async functions with exponential backoff + jitter."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=min_wait, max=max_wait, jitter=2),
        retry=retry_if_exception_type(retry_on),
        reraise=True,
    )

"""Per-domain rate limiting using token bucket algorithm."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field


# Default rate limits per domain
DOMAIN_LIMITS: dict[str, dict] = {
    "zillow.com": {"requests_per_minute": 10, "min_delay_seconds": 3.0, "max_delay_seconds": 7.0},
    "redfin.com": {"requests_per_minute": 15, "min_delay_seconds": 2.0, "max_delay_seconds": 5.0},
    "airbnb.com": {"requests_per_minute": 12, "min_delay_seconds": 2.5, "max_delay_seconds": 6.0},
    "vrbo.com": {"requests_per_minute": 12, "min_delay_seconds": 2.5, "max_delay_seconds": 6.0},
    "api.airdna.co": {"requests_per_minute": 30, "min_delay_seconds": 0.5, "max_delay_seconds": 1.5},
}


@dataclass
class DomainLimiter:
    """Rate limiter for a specific domain."""

    domain: str
    requests_per_minute: int = 15
    min_delay_seconds: float = 2.0
    max_delay_seconds: float = 5.0
    _last_request_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def acquire(self) -> None:
        """Wait until it's safe to make the next request."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time

            # Random delay within the configured range
            delay = random.uniform(self.min_delay_seconds, self.max_delay_seconds)

            if elapsed < delay:
                wait_time = delay - elapsed
                await asyncio.sleep(wait_time)

            self._last_request_time = time.monotonic()


class RateLimiter:
    """Manages rate limiters for multiple domains."""

    def __init__(self) -> None:
        self._limiters: dict[str, DomainLimiter] = {}

    def _get_limiter(self, domain: str) -> DomainLimiter:
        """Get or create a rate limiter for a domain."""
        if domain not in self._limiters:
            config = DOMAIN_LIMITS.get(domain, {})
            self._limiters[domain] = DomainLimiter(
                domain=domain,
                requests_per_minute=config.get("requests_per_minute", 15),
                min_delay_seconds=config.get("min_delay_seconds", 2.0),
                max_delay_seconds=config.get("max_delay_seconds", 5.0),
            )
        return self._limiters[domain]

    async def acquire(self, domain: str) -> None:
        """Wait for rate limit clearance for the given domain."""
        limiter = self._get_limiter(domain)
        await limiter.acquire()

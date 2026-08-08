"""Platform rate-limit awareness and circuit helpers for content adapters."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    rate_per_second: float
    capacity: float
    tokens: float = field(init=False)
    updated_at: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = self.capacity
        self.updated_at = time.monotonic()

    async def acquire(self) -> None:
        while True:
            now = time.monotonic()
            elapsed = now - self.updated_at
            self.updated_at = now
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate_per_second,
            )
            if self.tokens >= 1:
                self.tokens -= 1
                return
            await asyncio.sleep(max(0.05, (1 - self.tokens) / self.rate_per_second))


_buckets: dict[str, TokenBucket] = {}
_failures: dict[str, int] = defaultdict(int)


def get_bucket(platform: str, *, rate: float = 2.0, capacity: float = 5.0) -> TokenBucket:
    bucket = _buckets.get(platform)
    if bucket is None:
        bucket = TokenBucket(rate_per_second=rate, capacity=capacity)
        _buckets[platform] = bucket
    return bucket


async def throttle(platform: str) -> None:
    await get_bucket(platform).acquire()


def record_failure(platform: str) -> int:
    _failures[platform] += 1
    return _failures[platform]


def record_success(platform: str) -> None:
    _failures[platform] = 0


def failure_count(platform: str) -> int:
    return _failures[platform]

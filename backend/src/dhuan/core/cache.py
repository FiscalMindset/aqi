"""Last-good-value cache: fail soft, never fail silent.

Every feed read that reaches the API goes through here. If the upstream is
down, we serve the last good value together with its age in seconds, so the
UI can show a visible stale state. We never invent a value.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

from dhuan.core.logging import get_logger, log_event

logger = get_logger("cache")

T = TypeVar("T")


@dataclass(slots=True)
class CacheEntry(Generic[T]):
    value: T
    fetched_at: float = field(default_factory=time.time)

    def age_seconds(self) -> float:
        return time.time() - self.fetched_at


class TTLCache(Generic[T]):
    def __init__(self, maxsize: int = 256) -> None:
        self._store: dict[str, CacheEntry[T]] = {}
        self._maxsize = maxsize

    def get(self, key: str) -> T | None:
        entry = self._store.get(key)
        return entry.value if entry else None

    def get_entry(self, key: str) -> CacheEntry[T] | None:
        return self._store.get(key)

    def set(self, key: str, value: T) -> None:
        if len(self._store) >= self._maxsize:
            # evict oldest
            oldest = min(self._store.items(), key=lambda kv: kv[1].fetched_at)[0]
            del self._store[oldest]
        self._store[key] = CacheEntry(value)

    async def get_or_fetch(
        self, key: str, fetcher: Callable[[], Any], *, ttl_seconds: float = 60.0
    ) -> tuple[T, float, bool]:
        """Return `(value, age_seconds, is_stale)`; never raises on upstream failure."""
        entry = self.get_entry(key)
        if entry is not None and entry.age_seconds() < ttl_seconds:
            return entry.value, entry.age_seconds(), False
        try:
            value = await fetcher()
            self.set(key, value)
            return value, 0.0, False
        except Exception as exc:  # noqa: BLE001 - fail soft by design
            from dhuan.core.metrics import record

            record("CacheServedStale", 1)
            log_event(
                logger, 40 if entry is None else 30,
                "cache_fetch_failed_serving_last_good",
                key=key, error=str(exc), had_last_good=entry is not None,
            )
            if entry is None:
                raise
            return entry.value, entry.age_seconds(), True

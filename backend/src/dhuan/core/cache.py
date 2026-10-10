"""Last-good-value cache: fail soft, never fail silent.

Every feed read that reaches the API goes through here. If the upstream is
down, we serve the last good value together with its age in seconds, so the
UI can show a visible stale state. We never invent a value.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from dhuan.core.logging import get_logger, log_event
from dhuan.core.metrics import record

logger = get_logger("cache")


@dataclass(slots=True)
class CacheEntry[T]:
    value: T
    fetched_at: float = field(default_factory=time.time)

    def age_seconds(self) -> float:
        return time.time() - self.fetched_at


class TTLCache[T]:
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
            oldest = min(self._store.items(), key=lambda kv: kv[1].fetched_at)[0]
            del self._store[oldest]
        self._store[key] = CacheEntry(value)

    async def get_or_fetch(
        self, key: str, fetcher: Callable[[], Any], *, ttl_seconds: float = 60.0
    ) -> tuple[T, float, bool]:
        """Return `(value, age_seconds, is_stale)`; never swallows errors silently."""
        entry = self.get_entry(key)
        if entry is not None and entry.age_seconds() < ttl_seconds:
            return entry.value, entry.age_seconds(), False
        last_error: Exception | None = None
        try:
            value = await fetcher()
        except Exception as exc:  # fail soft by design (BLE001 intentionally not silenced globally)
            last_error = exc
            record("CacheServedStale", 1)
            log_event(
                logger,
                40 if entry is None else 30,
                "cache_fetch_failed_serving_last_good",
                key=key,
                error=str(exc),
                had_last_good=entry is not None,
            )
        else:
            self.set(key, value)
            return value, 0.0, False
        if entry is not None:
            return entry.value, entry.age_seconds(), True
        assert last_error is not None
        raise last_error

"""A cached client must survive the task that closed it.

The ingest clients are cached process-wide in api/deps.py and a Lambda
container serves many invocations, each in a fresh event loop. Closing the
client without replacing it left the cache holding a closed httpx client, so
every later invocation raised "Cannot send a request, as the client has been
closed" and the pipeline silently degraded that feed to a branch failure.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from dhuan.core.config import Settings
from dhuan.ingest.firms import FireClient
from dhuan.ingest.osm import OverpassClient
from dhuan.ingest.weather import WeatherClient


def _settings() -> Settings:
    return Settings(firms_map_key="test-key")


@pytest.mark.parametrize("factory", [FireClient, OverpassClient])
def test_client_is_reusable_after_aclose(factory: type[Any]) -> None:
    client = factory(_settings())
    asyncio.run(client.aclose())
    # The second task in the same container must not find a closed client.
    assert not client._client.is_closed
    asyncio.run(client.aclose())


def test_weather_client_is_reusable_after_aclose() -> None:
    client = WeatherClient(_settings())
    asyncio.run(client.aclose())
    assert not client._client.is_closed
    asyncio.run(client.aclose())


def test_repeat_runs_of_a_shared_client_keep_working() -> None:
    """The exact warm-container failure: task one closes, task two reuses."""
    from dhuan.api.deps import get_fires

    get_fires(_settings())

    async def task() -> str:
        client = get_fires(_settings())
        try:
            return "ok"
        finally:
            await client.aclose()

    assert asyncio.run(task()) == "ok"
    assert asyncio.run(task()) == "ok"

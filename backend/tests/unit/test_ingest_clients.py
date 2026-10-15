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


def test_dispatcher_tears_down_cached_clients_between_invocations() -> None:
    """Two tasks in one container must not share a dead client.

    The cache in api/deps.py is process-wide and each Lambda invocation runs its
    own event loop, so anything left cached is unusable for the next task. The
    dispatcher tears the cache down in a finally, which is what makes the second
    invocation behave like a fresh container.
    """
    from dhuan.api import deps
    from dhuan.pipeline import tasks

    calls: list[str] = []
    tasks.HANDLERS["_test"] = lambda _event: calls.append("ran") or {"ok": True}

    deps._clients["fires"] = FireClient(_settings())
    try:
        assert tasks.lambda_handler({"task": "_test"}) == {"ok": True}
        assert deps._clients == {}, "clients must not survive the invocation"
        # The whole point: the second task sees an empty cache, not a dead client.
        assert tasks.lambda_handler({"task": "_test"}) == {"ok": True}
        assert calls == ["ran", "ran"]
    finally:
        tasks.HANDLERS.pop("_test", None)
        deps._clients.clear()


def test_reset_clients_survives_a_broken_client() -> None:
    """Teardown must never mask the task result."""
    from dhuan.api import deps

    class Exploding:
        async def aclose(self) -> None:
            raise RuntimeError("nope")

    deps._clients["fires"] = Exploding()
    deps.reset_clients()
    assert deps._clients == {}


def test_airquality_client_is_reusable_after_aclose() -> None:
    from dhuan.ingest.airquality import AirQualityClient

    client = AirQualityClient(_settings())
    asyncio.run(client.aclose())
    assert not client._client.is_closed

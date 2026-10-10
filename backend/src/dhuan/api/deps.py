"""Shared dependencies: long-lived clients per process (Lambda reuses warm ones)."""

from __future__ import annotations

from typing import Any

from dhuan.core.cache import TTLCache
from dhuan.core.config import Settings, get_settings
from dhuan.ingest.firms import FireClient
from dhuan.ingest.openaq import OpenAQClient
from dhuan.ingest.weather import WeatherClient
from dhuan.store.dynamodb import FeedsStore
from dhuan.store.opensearch import SourceIndex

_clients: dict[str, Any] = {}


def get_openaq(settings: Settings | None = None) -> OpenAQClient:
    s = settings or get_settings()
    if "openaq" not in _clients:
        _clients["openaq"] = OpenAQClient(s)
    return _clients["openaq"]  # type: ignore[no-any-return]


def get_weather(settings: Settings | None = None) -> WeatherClient:
    s = settings or get_settings()
    if "weather" not in _clients:
        _clients["weather"] = WeatherClient(s)
    return _clients["weather"]  # type: ignore[no-any-return]


def get_fires(settings: Settings | None = None) -> FireClient:
    s = settings or get_settings()
    if "fires" not in _clients:
        _clients["fires"] = FireClient(s)
    return _clients["fires"]  # type: ignore[no-any-return]


def get_source_index(settings: Settings | None = None) -> SourceIndex:
    s = settings or get_settings()
    if "sources" not in _clients:
        _clients["sources"] = SourceIndex(s)
    return _clients["sources"]  # type: ignore[no-any-return]


def get_feeds_store(settings: Settings | None = None) -> FeedsStore:
    s = settings or get_settings()
    if "feeds" not in _clients:
        _clients["feeds"] = FeedsStore(s)
    return _clients["feeds"]  # type: ignore[no-any-return]


def get_station_cache() -> TTLCache[Any]:
    if "station_cache" not in _clients:
        _clients["station_cache"] = TTLCache[Any](maxsize=64)
    return _clients["station_cache"]  # type: ignore[no-any-return]


def get_weather_cache() -> TTLCache[Any]:
    if "weather_cache" not in _clients:
        _clients["weather_cache"] = TTLCache[Any](maxsize=64)
    return _clients["weather_cache"]  # type: ignore[no-any-return]


async def aclose_clients() -> None:
    for key in ("openaq", "weather", "fires"):
        client = _clients.pop(key, None)
        if client is not None:
            await client.aclose()
    index = _clients.pop("sources", None)
    if index is not None:
        index.close()

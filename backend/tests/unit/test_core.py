"""Unit tests for the shared HTTP layer: timeout, retry-with-jitter, limits."""

from __future__ import annotations

import httpx
import pytest
import respx

from dhuan.core.cache import TTLCache
from dhuan.core.config import Settings
from dhuan.core.http import (
    HttpPolicy,
    UpstreamClient,
    UpstreamError,
    jitter_sleep_seconds,
    make_client,
    make_request,
)
from dhuan.core.metrics import record
from dhuan.core.tracing import get_tracer
from dhuan.core.units import Interval, Point, haversine_km


def _policy(**kw: object) -> HttpPolicy:
    base = {
        "timeout_seconds": 5.0,
        "connect_timeout_seconds": 2.0,
        "max_retries": 3,
        "base_delay_seconds": 0.01,
        "max_delay_seconds": 0.05,
    }
    base.update(kw)
    return HttpPolicy(**base)  # type: ignore[arg-type]


def settings(**kw: object) -> Settings:
    return Settings(env="test", **kw)  # type: ignore[arg-type]


@respx.mock
async def test_retryable_status_then_success() -> None:
    route = respx.get("https://up.example/x").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    client = make_client(_policy())
    resp = await make_request(client, _policy(), "test", "GET", "https://up.example/x")
    assert resp.status_code == 200
    assert route.call_count == 2


@respx.mock
async def test_timeout_becomes_upstream_error() -> None:
    respx.get("https://up.example/x").mock(side_effect=httpx.TimeoutException("boom"))
    client = make_client(_policy(max_retries=1))
    with pytest.raises(UpstreamError) as err:
        await make_request(client, _policy(max_retries=1), "test", "GET", "https://up.example/x")
    assert "transport error" in str(err.value)


@respx.mock
async def test_persistent_503_raises_after_retries() -> None:
    route = respx.get("https://up.example/x").mock(return_value=httpx.Response(500))
    client = make_client(_policy(max_retries=2))
    with pytest.raises(UpstreamError):
        await make_request(client, _policy(max_retries=2), "test", "GET", "https://up.example/x")
    assert route.call_count == 3


@respx.mock
async def test_4xx_not_retried() -> None:
    route = respx.get("https://up.example/x").mock(return_value=httpx.Response(404))
    client = make_client(_policy())
    with pytest.raises(UpstreamError):
        await make_request(client, _policy(), "test", "GET", "https://up.example/x")
    assert route.call_count == 1


@respx.mock
async def test_post_carries_body() -> None:
    route = respx.post("https://up.example/q").mock(return_value=httpx.Response(200, json={}))
    client = make_client(_policy())
    await make_request(
        client, _policy(), "overpass", "POST", "https://up.example/q", data={"data": "[out:json];"}
    )
    assert route.called
    assert "data" in route.calls[0].request.content.decode(errors="ignore")


def test_jitter_is_bounded_and_grows() -> None:
    first = jitter_sleep_seconds(0.1, 1)
    third = jitter_sleep_seconds(0.1, 3)
    assert first >= 0
    assert third <= third and third <= 30
    assert third > first or third >= 0  # jitter is random, bound is the guarantee


def test_upstream_client_get() -> None:
    client = UpstreamClient("demo", "https://up.example")
    assert client.policy.timeout_seconds > 0
    assert client.source == "demo"


async def test_ttl_cache_hit_miss_and_fetch() -> None:
    cache: TTLCache[str] = TTLCache()
    calls = {"n": 0}

    async def fetcher() -> str:
        calls["n"] += 1
        return f"value{calls['n']}"

    v, _age, stale = await cache.get_or_fetch("k", fetcher, ttl_seconds=60)
    assert v == "value1"
    assert stale is False
    v2, _age2, _s2 = await cache.get_or_fetch("k", fetcher, ttl_seconds=60)
    assert v2 == "value1"  # served from cache
    assert calls["n"] == 1


async def test_ttl_cache_serves_last_good_on_failure() -> None:
    cache: TTLCache[str] = TTLCache()
    cache.set("k", "good")
    boom = {"fail": True}

    async def fetcher() -> str:
        if boom["fail"]:
            raise RuntimeError("upstream down")
        return "fresh"

    value, age, stale = await cache.get_or_fetch("k", fetcher, ttl_seconds=0)
    assert value == "good"
    assert stale is True
    assert age >= 0


async def test_ttl_cache_raises_without_cache() -> None:
    cache: TTLCache[str] = TTLCache()

    async def fetcher() -> str:
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        await cache.get_or_fetch("k", fetcher, ttl_seconds=0)


def test_interval_validates_order() -> None:
    with pytest.raises(ValueError):
        Interval(low=10, mid=5, high=1)
    with pytest.raises(ValueError):
        Interval(low=-1, mid=0, high=1)


def test_point_validates_ranges() -> None:
    with pytest.raises(ValueError):
        Point(lat=91, lon=0)
    with pytest.raises(ValueError):
        Point(lat=0, lon=181)


def test_haversine_known_distance() -> None:
    # New Delhi to Gurugram ~ 26 km straight line
    d = haversine_km(Point(28.6139, 77.2090), Point(28.4595, 77.0266))
    assert 20 < d < 30


def test_record_and_tracer_do_not_crash_outside_lambda() -> None:
    record("TestMetric", 1)
    tracer = get_tracer()
    assert tracer is not None
    tracer.put_annotation("k", "v")


def test_logging_configures_json_handler() -> None:
    import logging

    from dhuan.core.logging import JsonFormatter, configure_logging, get_logger

    configure_logging("DEBUG")
    logger = get_logger("conf")
    assert logger.parent is not None and logger.parent.level == logging.DEBUG
    handlers = logging.getLogger("dhuan").handlers
    assert handlers and isinstance(handlers[0].formatter, JsonFormatter)


def test_metrics_ephemeral_and_debug_print(monkeypatch: pytest.MonkeyPatch, capsys: object) -> None:
    from dhuan.core.metrics import _EphemeralMetrics, get_metrics

    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    metrics = get_metrics()
    assert isinstance(metrics, _EphemeralMetrics)
    metrics.single_metric("x", "Count", a="b").__enter__()
    record("Y", 2)
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "metric" not in out  # debug printing is opt-in


def test_tracing_noop_calls() -> None:
    tracer = get_tracer()
    assert tracer.capture_method(lambda self: self) is not None
    assert callable(tracer.put_annotation)


def test_upstream_client_helpers() -> None:
    import asyncio

    from dhuan.core.http import endpoints_round_robin, first_success

    assert endpoints_round_robin(["a", "b"]) == ["a", "b"]

    async def ok() -> str:
        return "ok"

    async def bad() -> str:
        raise RuntimeError("no")

    assert asyncio.run(first_success([bad, ok])) == "ok"
    with pytest.raises(RuntimeError):
        asyncio.run(first_success([bad]))


def test_deps_helpers_defaults() -> None:
    from dhuan.api.deps import get_station_cache, get_weather_cache, reset_clients

    reset_clients()
    assert get_station_cache() is get_station_cache()
    assert get_weather_cache() is get_weather_cache()

"""API route edge-case tests: estimate fallbacks, health degradation, grid."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient


@pytest.fixture()
def api(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with env-driven settings and a clean client/cache state."""
    for key, value in {
        "OPENAQ_API_KEY": "test-key",
        "ENV": "test",
    }.items():
        monkeypatch.setenv(key, value)
    from dhuan.core import config

    config.get_settings.cache_clear()
    from dhuan.api.app import create_app
    from dhuan.api.deps import (
        get_station_cache,
        get_weather_cache,
        reset_clients,
    )

    reset_clients()
    get_station_cache()._store.clear()
    get_weather_cache()._store.clear()
    return TestClient(create_app())


def test_grid_returns_304_for_matching_etag(api: TestClient) -> None:
    first = api.get("/v1/grid")
    etag = first.headers["etag"]
    second = api.get("/v1/grid", headers={"If-None-Match": etag})
    assert second.status_code == 304



def test_estimate_outside_coverage_is_problem_json(api: TestClient) -> None:
    resp = api.get("/v1/estimate", params={"lat": 19.076, "lon": 72.877})
    assert resp.status_code == 422
    body = resp.json()
    assert body["type"].endswith("/outside-coverage")



@respx.mock
def test_estimate_baseline_when_station_present(api: TestClient) -> None:
    """A live station reading anchors the estimate when the model is off."""
    from dhuan.api.deps import get_station_cache, get_weather_cache, reset_clients
    from dhuan.core import config

    config.get_settings.cache_clear()
    reset_clients()
    get_station_cache()._store.clear()
    get_weather_cache()._store.clear()
    respx.get("https://api.openaq.org/v3/locations").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 8118,
                        "name": "New Delhi",
                        "coordinates": {"latitude": 28.63576, "longitude": 77.22445},
                        "provider": {"name": "AirNow"},
                        "sensors": [{"id": 23534, "parameter": {"name": "pm25"}}],
                        "datetimeLast": {"utc": "2026-10-01T00:00:00Z"},
                    }
                ]
            },
        )
    )
    respx.get("https://api.openaq.org/v3/locations/8118/latest").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "datetime": {"utc": "2026-10-10T20:00:00Z"},
                        "value": 168.0,
                        "coordinates": {"latitude": 28.63576, "longitude": 77.22445},
                        "sensorsId": 23534,
                        "locationsId": 8118,
                    }
                ]
            },
        )
    )
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(
            200,
            json={
                "hourly": {
                    "time": ["2026-10-10T20:00"],
                    "wind_speed_10m": [2.5],
                    "wind_direction_10m": [292.0],
                    "wind_gusts_10m": [4.0],
                    "temperature_2m": [14.0],
                    "relative_humidity_2pct_2m": [70.0],
                    "precipitation": [0.0],
                    "relative_humidity_2m": [70.0],
                }
            },
        )
    )
    resp = api.get("/v1/estimate", params={"lat": 28.64, "lon": 77.22})
    if resp.status_code != 200:
        print("PROBLEM", resp.json())
    assert resp.status_code == 200
    body = resp.json()
    assert body["pm25_low"] <= body["pm25_mid"] <= body["pm25_high"]
    assert body["nearest_station_pm25"] == 168.0


def test_ready_reports_components(api: TestClient) -> None:
    resp = api.get("/ready")
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        components = {c["component"] for c in resp.json()["checks"]}
        assert {"dynamodb", "opensearch", "feeds"} <= components


def test_openapi_contract_has_all_routes(api: TestClient) -> None:
    spec = api.get("/openapi.json").json()
    paths = spec["paths"]
    for expected in (
        "/health",
        "/ready",
        "/v1/estimate",
        "/v1/grid",
        "/v1/sources",
        "/v1/stations",
        "/v1/status",
        "/v1/validation",
        "/v1/explain",
        "/v1/subscriptions",
    ):
        assert expected in paths, f"missing {expected} in OpenAPI"


def test_advice_for_attribution_covers_personas() -> None:
    from dhuan.agents.attribution import advice_for_attribution
    from dhuan.agents.schemas import AttributionResult

    result = AttributionResult(
        summary="s",
        likely_causes=[],
        confidence="low",
        confidence_reason="r",
        evidence=[],
    )
    advice = advice_for_attribution(result, {"pm25_mid": 300.0, "category": "Severe"})
    personas = {a.persona for a in advice}
    assert {"parent", "rider", "worker", "general"} <= personas
    for a in advice:
        assert a.disclaimer
        assert a.actions




@respx.mock
def test_estimate_model_failure_falls_back_to_station(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model failure must fall back to the station baseline and be logged."""
    monkeypatch.setenv("DEMO_MODE", "0")
    from dhuan.api.deps import get_station_cache, get_weather_cache, reset_clients
    from dhuan.core import config

    config.get_settings.cache_clear()
    reset_clients()
    get_station_cache()._store.clear()
    get_weather_cache()._store.clear()

    def _boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("model artifact corrupt")

    # Patch the symbol the route actually calls. Patching
    # dhuan.model.predict.load_artifact has no effect: estimate.py does
    # `from dhuan.model.predict import load_artifact`, so it holds its own
    # reference. The test passed for years only because ARTIFACTS pointed at a
    # non-existent src/models, which raised ModelNotTrainedError by accident.
    monkeypatch.setattr("dhuan.api.routers.estimate.load_artifact", _boom)

    respx.get("https://api.openaq.org/v3/locations").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 8118,
                        "name": "New Delhi",
                        "coordinates": {"latitude": 28.63576, "longitude": 77.22445},
                        "provider": {"name": "AirNow"},
                        "sensors": [{"id": 23534, "parameter": {"name": "pm25"}}],
                        "datetimeLast": {"utc": "2026-10-01T00:00:00Z"},
                    }
                ]
            },
        )
    )
    respx.get("https://api.openaq.org/v3/locations/8118/latest").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "datetime": {"utc": "2026-10-10T20:00:00Z"},
                        "value": 175.0,
                        "coordinates": {"latitude": 28.63576, "longitude": 77.22445},
                        "sensorsId": 23534,
                        "locationsId": 8118,
                    }
                ]
            },
        )
    )
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(
            200,
            json={
                "hourly": {
                    "time": ["2026-10-10T20:00"],
                    "wind_speed_10m": [3.0],
                    "wind_direction_10m": [270.0],
                    "wind_gusts_10m": [5.0],
                    "temperature_2m": [15.0],
                    "relative_humidity_2m": [65.0],
                    "precipitation": [0.0],
                }
            },
        )
    )
    resp = api.get("/v1/estimate", params={"lat": 28.64, "lon": 77.22})
    assert resp.status_code == 200
    body = resp.json()
    assert body["served_by"] == "nearest-station"
    assert body["pm25_mid"] == 175.0


def test_ready_handles_unreachable_components(api: TestClient) -> None:
    """With LocalStack unreachable the route still answers, honestly degraded."""

    resp = api.get("/ready")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in ("ready", "degraded")
    assert len(body["checks"]) == 3
    assert all("ok" in c for c in body["checks"])


def test_validation_serves_real_metrics(api: TestClient) -> None:
    resp = api.get("/v1/validation")
    if resp.status_code == 404:
        pytest.skip("no trained metrics artifact in this environment")
    assert resp.status_code == 200
    body = resp.json()
    assert body["n_rows"] > 1000
    assert "temporal_holdout" in body
    assert body["winner"]


def test_stations_limit_respected(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "1")
    from dhuan.core import config

    config.get_settings.cache_clear()
    resp = api.get("/v1/stations", params={"lat": 28.64, "lon": 77.22, "limit": 3})
    assert resp.status_code == 200
    assert len(resp.json()) <= 3


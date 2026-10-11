"""Unit tests for the API layer with mocked upstreams and stores."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from dhuan.api.app import create_app
from dhuan.core import config

OPENAQ_LOCATIONS_URL = "https://api.openaq.org/v3/locations"
OPENAQ_LATEST_URL = "https://api.openaq.org/v3/locations/8118/latest"
DEMO_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "demo"


@pytest.fixture()
def api(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with env-driven settings resolved before the app is created."""
    for key, value in {
        "OPENAQ_API_KEY": "test-key",
        "ENV": "test",
        "DEMO_DATA_DIR": str(DEMO_DIR),
        "DEMO_MODE": "0",
    }.items():
        monkeypatch.setenv(key, value)
    config.get_settings.cache_clear()
    from dhuan.api.deps import reset_clients

    reset_clients()  # drop any clients cached with different settings
    return TestClient(create_app())


def test_health_ok(api: TestClient) -> None:
    resp = api.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_openapi_published(api: TestClient) -> None:
    resp = api.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert "/v1/stations" in spec["paths"]
    assert spec["info"]["title"] == "Dhuan Detective"


def test_stations_outside_coverage_is_problem_json(api: TestClient) -> None:
    resp = api.get("/v1/stations", params={"lat": 19.076, "lon": 72.877})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["type"].endswith("/outside-coverage")
    assert body["correlation_id"]


def test_stations_requires_valid_numbers(api: TestClient) -> None:
    resp = api.get("/v1/stations", params={"lat": "abc", "lon": 77.2})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_correlation_id_echoed(api: TestClient) -> None:
    resp = api.get("/health", headers={"x-correlation-id": "test-cid-123"})
    assert resp.headers.get("x-correlation-id") == "test-cid-123"


def _past_iso(hours_ago: int = 2) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:00:00Z")


@respx.mock
def test_stations_serves_openaq_readings(api: TestClient) -> None:
    respx.get(OPENAQ_LOCATIONS_URL).mock(
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
                        "datetimeLast": {"utc": _past_iso(2)},
                    }
                ]
            },
        )
    )
    respx.get(OPENAQ_LATEST_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "datetime": {"utc": _past_iso(2)},
                        "value": 112.0,
                        "coordinates": {"latitude": 28.63576, "longitude": 77.22445},
                        "sensorsId": 23534,
                        "locationsId": 8118,
                    }
                ]
            },
        )
    )
    resp = api.get("/v1/stations", params={"lat": 28.65, "lon": 77.22})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["pm25"] == 112.0
    assert body[0]["category"] == "Poor"
    assert body[0]["age_seconds"] > 0


def test_stations_demo_mode_serves_recorded_data_with_flag(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_MODE", "1")
    config.get_settings.cache_clear()
    resp = api.get("/v1/stations", params={"lat": 28.65, "lon": 77.22})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 1
    # recorded data is real historical data: Jan 2024, so its age is large and honest
    assert body[0]["age_seconds"] > 0


def test_unhandled_route_404_is_problem(api: TestClient) -> None:
    resp = api.get("/v1/does-not-exist")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_validation_endpoint_serves_generated_metrics(api: TestClient) -> None:
    resp = api.get("/v1/validation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["n_rows"] > 1000
    assert "temporal_holdout" in body
    assert body["winner"]
    # the UI must be able to tell which producer shipped
    assert body["baselines"]["persistence-lag1h"]["mae"] > 0


def test_grid_endpoint_returns_geojson_with_etag(api: TestClient) -> None:
    resp = api.get("/v1/grid", params={"simplify": True})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/geo+json")
    assert resp.headers.get("etag")


def test_explain_rejects_outside_coverage(api: TestClient) -> None:
    resp = api.post("/v1/explain", json={"lat": 19.076, "lon": 72.877})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_explain_runs_deterministic_agent(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dhuan.core import config

    monkeypatch.setenv("DEMO_MODE", "1")
    config.get_settings.cache_clear()
    resp = api.post("/v1/explain", json={"lat": 28.6139, "lon": 77.2090})
    assert resp.status_code == 200
    body = resp.json()
    assert body["served_by"] == "scripted-deterministic"
    attr = body["attribution"]
    assert attr["summary"]
    assert attr["evidence"], "attribution must carry tool evidence"
    ids = {e["evidence_id"] for e in attr["evidence"]}
    for cause in attr["likely_causes"]:
        assert set(cause["evidence_ids"]) <= ids, "every claim cites a real evidence id"
    assert "likely" in attr["summary"].lower()
    assert {a["persona"] for a in body["advice"]} >= {"parent", "rider", "worker"}
    for a in body["advice"]:
        assert a["disclaimer"]


def test_estimate_endpoint_demo_mode(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from dhuan.core import config

    monkeypatch.setenv("DEMO_MODE", "1")
    config.get_settings.cache_clear()
    resp = api.get("/v1/estimate", params={"lat": 28.6139, "lon": 77.2090})
    assert resp.status_code == 200
    body = resp.json()
    assert body["pm25_low"] <= body["pm25_mid"] <= body["pm25_high"]
    assert body["honesty"].startswith("Estimate, not a measurement")
    assert body["demo_mode"] is True

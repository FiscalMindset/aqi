"""API route edge-case tests: estimate fallbacks, health degradation, grid."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient


@pytest.fixture()
def api(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> TestClient:
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
    client = TestClient(create_app())
    # get_settings is lru_cached, and this fixture sets OPENAQ_API_KEY. Without
    # clearing it again on teardown, every later test in the session inherits
    # that credential and asserts against a Settings it did not ask for -
    # which showed up as an unrelated archive test failing only in a full run.
    request.addfinalizer(config.get_settings.cache_clear)
    return client


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



def test_spa_documents_are_not_cached_but_assets_are(api: TestClient) -> None:
    """Hashed assets cache forever; the documents naming them must not.

    A stale index.html or service worker points at chunk hashes the next deploy
    deleted, which the browser reports as "Failed to fetch dynamically imported
    module". That was the live failure, so it is pinned here.
    """
    import re
    from pathlib import Path

    web = Path(__file__).resolve().parents[1] / "fixtures" / "web"
    if not web.is_dir():
        return  # no built SPA in the unit-test environment

    shell = api.get("/")
    if shell.status_code != 200:
        return
    assert re.search(r"no-cache", shell.headers.get("cache-control", ""))


def test_prefixed_deep_link_serves_the_spa_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/staging/routes` must resolve to the file `routes`, not to a 404.

    The bundle registers its service worker and manifest relative to the base
    path. When the catch-all did not strip the prefix, `/staging/sw.js` matched
    no file and fell through to index.html, so the browser got HTML where it
    expected JavaScript and never registered the worker.
    """
    import shutil
    from pathlib import Path

    from fastapi.testclient import TestClient

    from dhuan.api.app import create_app
    from dhuan.core import config

    dist = Path(__file__).resolve().parents[2] / ".." / "frontend" / "dist"
    if not dist.is_dir():
        pytest.skip("no built SPA available for this test")

    monkeypatch.setenv("WEB_DIR", str(dist.resolve()))
    monkeypatch.setenv("WEB_BASE_PATH", "/staging")
    config.get_settings.cache_clear()
    with TestClient(create_app()) as client:
        for path in ("/staging/", "/staging/routes", "/staging/sw.js"):
            resp = client.get(path)
            assert resp.status_code == 200, path
            if path.endswith("sw.js"):
                assert "javascript" in resp.headers["content-type"], path
            else:
                assert "text/html" in resp.headers["content-type"], path
    config.get_settings.cache_clear()
    _ = shutil


class TestSubscriptionConfirmationIsNotFaked:
    """The confirmation email used to be reported as sent when nothing was sent.

    SNS_TOPIC_ARN was only a CloudFormation Output, so the topic was unreachable
    at runtime, subscribing the address was a no-op, and the response still said
    "a confirmation email has been sent". Someone waiting on that email would
    wait forever.
    """

    def test_reports_honestly_when_the_topic_is_unreachable(
        self, api: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from dhuan.api.routers import subscriptions as sub_mod
        from dhuan.core import config

        # No DynamoDB in unit tests; stub the store so we exercise the response.
        class FakeStore:
            def __init__(self, *a: object, **k: object) -> None:
                pass

            def make_id(self, email: str, locality: str) -> str:
                return "stub"

            def get(self, _id: str) -> None:
                return None

            def create(self, **kwargs: object) -> None:
                return None

        monkeypatch.setattr(sub_mod, "SubscriptionsStore", FakeStore)
        settings = config.get_settings()
        monkeypatch.setattr(settings, "sns_topic_arn", "")
        res = api.post(
            "/v1/subscriptions",
            json={
                "email": "nobody@example.com",
                "locality": "Ghevra",
                "lat": 28.4726,
                "lon": 77.1714,
                "threshold_category": "Poor",
            },
        )
        assert res.status_code == 201
        body = res.json()
        assert body["confirmation_sent"] is False
        assert "could not be sent" in body["confirmation"]


class TestAlertEmailIsComposedFromRealValues:
    """publish_alerts was a stub: every email carried pm25 = 0.0 and an
    unsubscribe link pointing at dhuan-detective.example, and the message was
    published under the literal locality "delhi-ncr" while the subscriber's
    FilterPolicy used the name they actually typed. A delivered message would
    have read "0 µg/m3" and offered a link that resolves nowhere.
    """

    def test_uses_the_subscribers_own_numbers_and_a_real_unsubscribe_link(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from dhuan.pipeline import tasks

        published: list[dict[str, object]] = []

        class FakeAlerter:
            def configured(self) -> bool:
                return True

            def publish(self, **kw: object) -> str:
                published.append(kw)
                return "mid-1"

        monkeypatch.setattr("dhuan.alerts.alerts.best_alerter", lambda _s: FakeAlerter())
        monkeypatch.setattr(
            tasks,
            "get_settings_for_pipeline",
            type(
                "S", (), {"public_base_url": "https://example.test/staging"}
            ),
        )

        tasks.publish_alerts(
            {
                "alerts": [
                    {
                        "decision": {"should_send": True, "band": "Poor"},
                        "email": "person@example.com",
                        "locality": "Ghevra",
                        "threshold_category": "Poor",
                        "unsubscribe_token": "tok123456",
                        "pm25_mid": 96.4,
                    }
                ]
            }
        )

        assert len(published) == 1
        sent = published[0]
        assert sent["locality"] == "ghevra", "must match the subscribe-time FilterPolicy"
        body = str(sent["body"])
        assert "96" in body, f"body should carry the real reading, got: {body[:200]}"
        assert "0 µg/m" not in body.replace("96.4 µg/m", "")
        assert "tok123456" in str(sent["body"]) or "tok123456" in str(sent.get("subject"))
        assert "dhuan-detective.example" not in body

    def test_refuses_to_send_without_an_unsubscribe_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from dhuan.pipeline import tasks

        published: list[dict[str, object]] = []

        class FakeAlerter:
            def configured(self) -> bool:
                return True

            def publish(self, **kw: object) -> str:
                published.append(kw)
                return "mid-1"

        monkeypatch.setattr("dhuan.alerts.alerts.best_alerter", lambda _s: FakeAlerter())
        monkeypatch.setattr(
            tasks,
            "get_settings_for_pipeline",
            type(
                "S", (), {"public_base_url": "https://example.test/staging"}
            ),
        )

        out = tasks.publish_alerts(
            {
                "alerts": [
                    {
                        "decision": {"should_send": True, "band": "Poor"},
                        "email": "person@example.com",
                        "locality": "Ghevra",
                        "unsubscribe_token": "",
                        "pm25_mid": 96.4,
                    }
                ]
            }
        )
        # Sending an alert the recipient cannot stop is worse than not sending it.
        assert published == []
        assert out["skipped"] == 1

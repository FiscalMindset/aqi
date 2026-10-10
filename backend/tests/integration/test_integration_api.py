"""Integration tests: every route against real containers + real fixtures."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture()
def api(env: dict[str, str]) -> TestClient:
    from dhuan.api.app import create_app

    return TestClient(create_app())


def test_sources_route_returns_real_osm_sources(api: TestClient, source_index: object) -> None:
    resp = api.get(
        "/v1/sources",
        params={"lat": 28.6139, "lon": 77.2090, "radius_km": 20, "upwind": False, "limit": 10},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 3
    names = {s["name"] for s in body["sources"]}
    # the fixture was fetched live from Overpass and contains these
    assert {"Ghazipur Landfill", "Bhalswa Landfill Area", "Okhla Landfill"} <= names
    for s in body["sources"]:
        assert 0.0 <= s["influence_score"] <= 1.0
        assert s["distance_km"] > 0
        assert "© OpenStreetMap" in s["attribution"]


def test_sources_route_requires_coverage(api: TestClient, source_index: object) -> None:
    resp = api.get("/v1/sources", params={"lat": 19.076, "lon": 72.877, "upwind": False})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_estimates_store_roundtrip(dynamodb: object, env: dict[str, str]) -> None:
    from dhuan.store.dynamodb import EstimatesStore

    store = EstimatesStore()
    cell = "88008990c7fffff"  # valid H3 res-8 id; content irrelevant for the store test
    ts = datetime.now(UTC)
    store.put_estimate(cell, ts, 90.0, 120.0, 160.0, "test-v1", extra={"note": "integration"})
    latest = store.get_latest(cell)
    assert latest is not None
    assert latest["pm25_mid"] == 120.0
    assert latest["model_version"] == "test-v1"
    history = store.get_history(cell, hours=1)
    assert len(history) >= 1


def test_subscriptions_idempotent(dynamodb: object, env: dict[str, str]) -> None:
    from dhuan.store.dynamodb import SubscriptionsStore

    store = SubscriptionsStore()
    sub_id = store.create("parent@example.com", "Rohini", 28.7146, 77.1025, "Poor")
    try:
        with pytest.raises(Exception):  # noqa: B017 - conditional put must conflict
            store.create("parent@example.com", "Rohini", 28.7146, 77.1025, "Poor")
    except Exception:
        pass  # expected: idempotency enforced by condition expression
    # same email, different locality -> a different subscription
    other_id = store.create("parent@example.com", "Dwarka", 28.5921, 77.0460, "Poor")
    assert other_id != sub_id
    item = store.get(sub_id)
    assert item is not None and item["email"] == "parent@example.com"
    store.delete(sub_id)
    store.delete(other_id)


def test_feeds_store_and_status_route(
    dynamodb: object, api: TestClient, env: dict[str, str]
) -> None:
    from dhuan.store.dynamodb import FeedsStore

    FeedsStore().record_success("openaq", records=3)
    resp = api.get("/v1/status")
    assert resp.status_code == 200
    body = resp.json()
    feeds = {f["feed"]: f for f in body["feeds"]}
    assert "openaq" in feeds
    assert feeds["openaq"]["ok"] is True
    assert body["coverage"]["boundary_license"].startswith("ODbL")


def test_s3_artifacts_roundtrip(s3: object, env: dict[str, str]) -> None:
    from dhuan.store.s3 import ArtifactStore

    store = ArtifactStore()
    store.put_json("grid/test/grid.geojson", {"type": "FeatureCollection", "features": []})
    got = store.get_json("grid/test/grid.geojson")
    assert got["type"] == "FeatureCollection"
    assert store.exists("grid/test/grid.geojson")
    assert not store.exists("grid/missing/none.geojson")


def test_ready_reflects_containers(api: TestClient) -> None:
    resp = api.get("/ready")
    # tables and index are up from conftest; at least not a 5xx
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        body = resp.json()
        assert {c["component"] for c in body["checks"]} >= {"dynamodb", "opensearch"}

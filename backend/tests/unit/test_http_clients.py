"""HTTP client + agent assembly tests."""

from __future__ import annotations

import httpx
import respx

from dhuan.core.config import Settings
from dhuan.core.http import UpstreamClient
from dhuan.ingest.osm import OverpassClient, build_query, parse_overpass


@respx.mock
async def test_upstream_client_get_parses() -> None:
    respx.get("https://up.example/api").mock(return_value=httpx.Response(200, json={"a": 1}))
    client = UpstreamClient("demo", "https://up.example")
    resp = await client.get("/api")
    assert resp.status_code == 200
    assert resp.json() == {"a": 1}
    await client.aclose()


@respx.mock
async def test_overpass_rotates_mirrors() -> None:
    respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=httpx.Response(504)
    )
    respx.post("https://overpass.private.coffee/api/interpreter").mock(
        return_value=httpx.Response(200, json={"elements": []})
    )
    settings = Settings(
        env="test",
        overpass_endpoints=[
            "https://overpass-api.de/api/interpreter",
            "https://overpass.private.coffee/api/interpreter",
        ],
    )
    client = OverpassClient(settings)
    payload = await client.query("[out:json];node(1);out;")
    assert payload == {"elements": []}
    await client.aclose()


def test_build_query_contains_all_types() -> None:
    ql = build_query(76.8, 28.4, 77.4, 28.9)
    assert "landfill" in ql
    assert "industrial" in ql
    assert "construction" in ql
    assert "traffic_signals" in ql
    assert "out geom" in ql


def test_parse_overpass_handles_relations_gracefully() -> None:
    docs = parse_overpass(
        {"elements": [{"type": "relation", "id": 1, "tags": {"landuse": "landfill"}}]},
        "2026-10-15T00:00:00+00:00",
    )
    assert docs == []

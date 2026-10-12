"""Tests for the cleanest-route comparison.

OSRM is mocked: the point is the sampling maths, the ranking and the failure
handling, not the live road network. `tests/contract` covers the live shape.
"""

from __future__ import annotations

import json
import re
from itertools import pairwise
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from dhuan.core.config import get_settings
from dhuan.core.units import Point
from dhuan.ingest.osrm import RouteCandidate, sample_along, straight_line_fallback

# The corridor comparison samples the model along each route, which needs real
# station readings. These tests previously leaned on DEMO_MODE for that; with
# demo mode gone the same facts come from a mocked OpenAQ station instead.
_STATION_LAT, _STATION_LON = 28.63576, 77.22445


def _mock_openaq(value: float = 168.0, lat: float | None = None) -> None:
    """A single official station that the corridor sampling can anchor to."""
    station_lat = _STATION_LAT if lat is None else lat
    respx.get("https://api.openaq.org/v3/locations").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 8118,
                        "name": "New Delhi",
                        "coordinates": {"latitude": station_lat, "longitude": _STATION_LON},
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
                        "value": value,
                        "coordinates": {"latitude": station_lat, "longitude": _STATION_LON},
                        "sensorsId": 23534,
                        "locationsId": 8118,
                    }
                ]
            },
        )
    )


class TestSampling:
    def test_endpoints_are_always_kept(self) -> None:
        line = [(77.0, 28.6), (77.001, 28.6), (77.002, 28.6)]
        pts = sample_along(line, spacing_m=500.0)
        assert pts[0].lon == pytest.approx(77.0)
        assert pts[-1].lon == pytest.approx(77.002)

    def test_samples_are_evenly_spaced(self) -> None:
        # roughly 1.1 km of east-west longitude at this latitude
        line = [(77.0, 28.6), (77.01, 28.6)]
        pts = sample_along(line, spacing_m=200.0)
        assert len(pts) >= 5
        gaps = [
            ((b.lat - a.lat) ** 2 + (b.lon - a.lon) ** 2) ** 0.5 for a, b in pairwise(pts)
        ]
        # no huge holes: the last step may be short, but nothing should be empty
        assert max(gaps) < 0.005

    def test_single_point_geometry(self) -> None:
        assert len(sample_along([(77.0, 28.6)], 500.0)) == 1

    def test_empty_geometry(self) -> None:
        assert sample_along([], 500.0) == []


class TestStraightLineFallback:
    def test_is_labelled_and_has_a_midpoint(self) -> None:
        routes = straight_line_fallback(Point(lat=28.6, lon=77.1), Point(lat=28.7, lon=77.2))
        assert len(routes) == 1
        assert routes[0].kind == "straight-line"
        assert len(routes[0].samples) == 3
        assert routes[0].distance_m > 0


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Same client fixture as test_api_routes: env-driven settings, clean caches."""
    for key, value in {
        "OPENAQ_API_KEY": "test-key",
        "ENV": "test",
    }.items():
        monkeypatch.setenv(key, value)
    from dhuan.core import config

    config.get_settings.cache_clear()
    from dhuan.api.app import create_app
    from dhuan.api.deps import get_station_cache, get_weather_cache, reset_clients

    reset_clients()
    get_station_cache()._store.clear()
    get_weather_cache()._store.clear()
    return TestClient(create_app())


def _osrm_route(coordinates: list[list[float]], distance: float, duration: float) -> dict[str, Any]:
    return {
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "distance": distance,
        "duration": duration,
    }


class TestCompareEndpoint:
    @staticmethod
    def _weather_mock() -> None:
        """Every sampled point needs weather; tests have no network."""
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
                        "surface_pressure": [1012.0],
                    }
                },
            )
        )

    @staticmethod
    def _osrm_mock(router: respx.Route | None) -> None:
        """Intercept only OSRM.

        Patching httpx.AsyncClient globally would also break the Open-Meteo and
        OpenAQ calls each sample needs, so every sample failed and the endpoint
        correctly returned 503.
        """
        url = re.compile(r"^https://router\.project-osrm\.org/.*")
        if router is None:
            respx.get(url).mock(side_effect=httpx.ConnectError("router down"))
        else:
            respx.get(url).mock(
                return_value=httpx.Response(200, json={"code": "Ok", "routes": router})
            )

    @respx.mock
    def test_ranks_by_exposure_not_by_distance(self, api: TestClient) -> None:
        """The whole point: the longer route can be the cleaner one."""
        _mock_openaq()
        short_dirty = _osrm_route(
            [[77.209, 28.6139], [77.19, 28.65], [77.1025, 28.7146]], 9000, 600
        )
        long_clean = _osrm_route(
            [[77.209, 28.6139], [77.16, 28.60], [77.09, 28.66], [77.1025, 28.7146]],
            14000, 900,
        )
        self._weather_mock()
        self._osrm_mock([short_dirty, long_clean])

        r = api.post(
            "/v1/routes/compare",
            json={
                "from_lat": 28.6139, "from_lon": 77.209,
                "to_lat": 28.7146, "to_lon": 77.1025,
                "max_samples": 5,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["router"] == "osrm"
        assert body["corridor_count"] == 2
        # whichever wins, ranks must be 1 and 2 and ordered by mean_pm25
        assert body["cleanest"]["rank"] == 1
        assert body["worst"]["rank"] == 2
        assert body["cleanest"]["mean_pm25"] <= body["worst"]["mean_pm25"]
        assert body["note"]
        assert "not measured" in body["note"]

    @respx.mock
    def test_router_failure_falls_back_and_says_so(self, api: TestClient) -> None:
        _mock_openaq()
        self._weather_mock()
        self._osrm_mock(None)
        r = api.post(
            "/v1/routes/compare",
            json={
                "from_lat": 28.6139, "from_lon": 77.209,
                "to_lat": 28.7146, "to_lon": 77.1025,
                "max_samples": 4,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["router"] == "straight-line-fallback"
        assert body["cleanest"]["kind"] == "straight-line"
        assert "not real roads" in body["honesty_note"]

    def test_endpoint_outside_coverage_is_rejected(
        self, api: TestClient
    ) -> None:
        r = api.post(
            "/v1/routes/compare",
            json={
                "from_lat": 28.6139, "from_lon": 77.209,
                "to_lat": 12.9716, "to_lon": 77.5946,  # Bengaluru
                "max_samples": 4,
            },
        )
        assert r.status_code == 422
        assert "outside" in json.dumps(r.json()).lower()

    def test_rejects_impossible_coordinates(self, api: TestClient) -> None:
        r = api.post(
            "/v1/routes/compare",
            json={
                "from_lat": 999, "from_lon": 77.209,
                "to_lat": 28.7146, "to_lon": 77.1025,
            },
        )
        assert r.status_code == 422


class TestRouteCandidate:
    def test_defaults_to_road(self) -> None:
        c = RouteCandidate(distance_m=1000, duration_s=60, geometry=[(77.0, 28.6), (77.1, 28.7)])
        assert c.kind == "road"
        assert c.samples == []


def test_settings_has_osrm_base() -> None:
    assert get_settings().osrm_base_url.startswith("https://")

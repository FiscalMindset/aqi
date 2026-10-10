"""Unit tests for the four ingest clients.

Live upstreams are mocked with `respx` using recorded/real sample payloads
stored under tests/fixtures (recorded data is allowed there; see AGENTS.md).
Each test also pins the request shape (URL, params, headers) so a silent API
change fails the build instead of silently returning nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from dhuan.core.config import Settings
from dhuan.core.http import UpstreamError
from dhuan.ingest.firms import FireClient
from dhuan.ingest.openaq import NotConfiguredError, OpenAQClient
from dhuan.ingest.osm import OverpassClient, parse_overpass
from dhuan.ingest.weather import WeatherClient

FIXTURES = Path(__file__).parent.parent / "fixtures"
FIRMS_NCR_URL = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
    "test-map-key/VIIRS_SNPP_NRT/75.8,27.5,78.5,30.5/3"
)


def _settings(**overrides: object) -> Settings:
    base = {
        "openaq_api_key": "test-key",
        "firms_map_key": "test-map-key",
        "env": "test",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text())  # type: ignore[no-any-return]


# ---------------------------------------------------------------- OpenAQ ---


@respx.mock
async def test_openaq_nearby_stations_parses_and_sends_key() -> None:
    payload = {
        "results": [
            {
                "id": 8118,
                "name": "New Delhi",
                "coordinates": {"latitude": 28.63576, "longitude": 77.22445},
                "provider": {"name": "AirNow"},
                "sensors": [
                    {"id": 23534, "parameter": {"name": "pm25"}},
                ],
                "datetimeLast": {"utc": "2024-12-13T14:30:00Z"},
            }
        ]
    }
    route = respx.get("https://api.openaq.org/v3/locations").mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = OpenAQClient(_settings())
    stations = await client.nearby_stations(28.6, 77.2, radius_m=1000)
    assert len(stations) == 1
    st = stations[0]
    assert st.station_id == "8118"
    assert st.pm25_sensor_id == 23534
    assert abs(st.location.lat - 28.63576) < 1e-6
    assert st.last_reading_at is not None
    request = route.calls[0].request
    assert request.headers["X-API-Key"] == "test-key"
    assert "radius=1000" in str(request.url)


async def test_openaq_refuses_without_key() -> None:
    client = OpenAQClient(_settings(openaq_api_key=""))
    with pytest.raises(NotConfiguredError):
        await client.nearby_stations(28.6, 77.2)


@respx.mock
async def test_openaq_latest_parses_readings() -> None:
    payload = {
        "results": [
            {
                "datetime": {"utc": "2024-09-25T22:00:00Z", "local": "x"},
                "value": 29.0,
                "coordinates": {"latitude": 28.6353, "longitude": -106.58},
                "sensorsId": 23534,
                "locationsId": 8118,
            }
        ]
    }
    respx.get("https://api.openaq.org/v3/locations/8118/latest").mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = OpenAQClient(_settings())
    readings = await client.latest_for_location(8118)
    assert len(readings) == 1
    assert readings[0].value == 29.0
    assert readings[0].age_seconds() > 0


@respx.mock
async def test_openaq_retries_then_raises_on_persistent_500() -> None:
    route = respx.get("https://api.openaq.org/v3/locations/8118/latest").mock(
        return_value=httpx.Response(500)
    )
    client = OpenAQClient(_settings())
    with pytest.raises(UpstreamError):
        await client.latest_for_location(8118)
    # 1 try + 3 retries (max_retries default 3)
    assert route.call_count == 4


# --------------------------------------------------------------- weather ---


@respx.mock
async def test_weather_forecast_parses_recorded_payload() -> None:
    fx = _fixture("openmeteo_forecast_sample.json")
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(200, json=fx)
    )
    client = WeatherClient(_settings())
    hours = await client.forecast(28.6139, 77.2090, days=2)
    assert len(hours) == 48
    first = hours[0]
    assert first.wind_speed_ms >= 0
    assert 0 <= first.wind_direction_deg <= 360
    # IST offset retained (not silently treated as UTC)
    assert first.observed_at.utcoffset().total_seconds() == 5.5 * 3600


@respx.mock
async def test_weather_historical_queries_archive_host() -> None:
    fx = _fixture("openmeteo_archive_sample.json")
    route = respx.get("https://archive-api.open-meteo.com/v1/archive").mock(
        return_value=httpx.Response(200, json=fx)
    )
    client = WeatherClient(_settings())
    hours = await client.historical(28.6139, 77.2090, "2024-01-01", "2024-01-02")
    assert len(hours) == 48
    request = route.calls[0].request
    assert "start_date=2024-01-01" in str(request.url)
    assert "timezone=Asia%2FKolkata" in str(request.url)


@respx.mock
async def test_weather_skips_hours_with_missing_wind() -> None:
    payload = {
        "hourly": {
            "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
            "wind_speed_10m": [2.0, None],
            "wind_direction_10m": [180.0, 90.0],
            "wind_gusts_10m": [None, None],
            "temperature_2m": [12.0, 13.0],
            "relative_humidity_2m": [80.0, 82.0],
            "precipitation": [0.0, 0.0],
        }
    }
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = WeatherClient(_settings())
    hours = await client.forecast(28.6, 77.2, days=1)
    assert len(hours) == 1  # the hour with no wind is dropped, not invented


# ---------------------------------------------------------------- FIRMS ---


FIRMS_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,"
    "instrument,confidence,version,bright_ti5,frp,daynight\n"
"28.20028,77.05177,330.45,0.41,0.37,2026-10-05,149,N,VIIRS,n,2.0NRT,298.86,3.11,N\n"
    "27.31573,77.90000,309.67,0.41,0.45,2026-10-06,130,N,VIIRS,n,2.0NRT,297.57,0.83,N\n"
)


@respx.mock
async def test_firms_parses_csv_and_builds_url() -> None:
    route = respx.get(
        "https://firms.modaps.eosdis.nasa.gov/api/area/csv/test-map-key/VIIRS_SNPP_NRT/75.8,27.5,78.5,30.5/3"
    ).mock(return_value=httpx.Response(200, text=FIRMS_CSV))
    client = FireClient(_settings())
    fires = await client.recent_in_ncr(day_range=3)
    assert len(fires) == 2
    assert fires[0].latitude == 28.20028
    assert fires[0].source == "VIIRS_SNPP_NRT"
    assert route.called


async def test_firms_refuses_without_key() -> None:
    client = FireClient(_settings(firms_map_key=""))
    with pytest.raises(NotConfiguredError):
        await client.recent_in_ncr()


@respx.mock
async def test_firms_empty_response_is_empty_list() -> None:
    respx.get(FIRMS_NCR_URL).mock(return_value=httpx.Response(200, text=""))
    client = FireClient(_settings())
    assert await client.recent_in_ncr() == []


# ------------------------------------------------------------------- OSM ---


async def test_parse_overpass_real_fixture() -> None:
    payload = _fixture("overpass_sample.json")
    docs = parse_overpass(payload, "2026-10-15T00:00:00+00:00")
    assert len(docs) >= 10
    names = {d.name for d in docs}
    assert "Ghazipur Landfill" in names
    assert "Bhalswa Landfill Area" in names
    assert "Okhla Landfill" in names
    for d in docs:
        assert d.osm_id.startswith(("way/", "node/"))
        assert "ODbL" in d.to_index_dict()["attribution"]
    landfills = [d for d in docs if d.type == "landfill"]
    assert any(d.area_m2 and d.area_m2 > 1000 for d in landfills)


async def test_parse_overpass_classifies_junctions() -> None:
    payload = {"elements": [{"type": "node", "id": 42, "lat": 28.6, "lon": 77.2,
                             "tags": {"highway": "traffic_signals"}}]}
    docs = parse_overpass(payload, "2026-10-15T00:00:00+00:00")
    assert docs[0].type == "major_junction"
    assert docs[0].name == "Signalised junction"


@respx.mock
async def test_overpass_rotates_mirrors_on_failure() -> None:
    first = respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=httpx.Response(504)
    )
    second = respx.post("https://overpass.kumi.systems/api/interpreter").mock(
        return_value=httpx.Response(200, json={"elements": []})
    )
    client = OverpassClient(_settings(overpass_endpoints=[
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]))
    payload = await client.query("[out:json];node(1);out;")
    assert payload == {"elements": []}
    assert first.called and second.called


@respx.mock
async def test_overpass_all_mirrors_down_raises() -> None:
    respx.post("https://overpass-api.de/api/interpreter").mock(return_value=httpx.Response(500))
    respx.post("https://overpass.kumi.systems/api/interpreter").mock(
        return_value=httpx.Response(500)
    )
    client = OverpassClient(_settings(overpass_endpoints=[
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]))
    with pytest.raises(Exception):  # noqa: B017 - mirrors exhausted
        await client.query("[out:json];node(1);out;")

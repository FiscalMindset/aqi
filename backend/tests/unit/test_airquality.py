"""Tests for the Open-Meteo air-quality cross-check client.

Every test pins the real URL and query so a silent upstream change fails here
rather than in production. The fixture is a recorded real response.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from dhuan.core.config import get_settings
from dhuan.core.units import Point
from dhuan.ingest.airquality import AIR_QUALITY_URL, AirQualityClient
from dhuan.ingest.types import AirQualityObservation

FIXTURE = Path(__file__).parents[1] / "fixtures" / "openmeteo_airquality_sample.json"
GHEVRA = Point(lat=28.4726, lon=77.1714)


def _payload() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text())
    data.pop("_provenance", None)
    return data


@pytest.mark.anyio
@respx.mock
async def test_requests_the_documented_endpoint_and_needs_no_key() -> None:
    route = respx.get(AIR_QUALITY_URL).mock(
        return_value=httpx.Response(200, json=_payload())
    )
    await AirQualityClient().current(GHEVRA)

    assert route.called
    url = str(route.calls[0].request.url)
    assert "latitude=28.4726" in url
    assert "longitude=77.1714" in url
    assert "timezone=Asia%2FKolkata" in url
    for var in ("pm2_5", "pm10", "dust", "us_aqi", "european_aqi"):
        assert var in url
    # The whole point: this feed must never require a credential.
    assert "key=" not in url
    assert "apikey=" not in url


@pytest.mark.anyio
@respx.mock
async def test_parses_hourly_rows_with_provenance() -> None:
    respx.get(AIR_QUALITY_URL).mock(return_value=httpx.Response(200, json=_payload()))
    rows = await AirQualityClient().current(GHEVRA)

    assert len(rows) == 24
    first = rows[0]
    assert first.observed_at.isoformat() == "2026-10-14T00:00:00+05:30"
    assert first.pm25 == pytest.approx(73.3)
    assert first.dust == pytest.approx(102.0)
    assert first.us_aqi == pytest.approx(159.0)
    assert "CAMS" in first.provider


@pytest.mark.anyio
@respx.mock
async def test_drops_rows_where_everything_is_null_rather_than_inventing_zeros() -> None:
    payload = _payload()
    hourly = payload["hourly"]
    hourly["pm2_5"][3] = None
    hourly["pm10"][3] = None
    hourly["dust"][3] = None
    hourly["us_aqi"][3] = None
    hourly["european_aqi"][3] = None
    respx.get(AIR_QUALITY_URL).mock(return_value=httpx.Response(200, json=payload))

    rows = await AirQualityClient().current(GHEVRA)

    assert len(rows) == 23, "an all-missing hour must be dropped, not read as zero"
    assert all(r.pm25 is not None for r in rows)


@pytest.mark.anyio
@respx.mock
async def test_a_blocked_row_is_kept_with_its_other_values() -> None:
    payload = _payload()
    payload["hourly"]["pm2_5"][5] = None
    respx.get(AIR_QUALITY_URL).mock(return_value=httpx.Response(200, json=payload))

    rows = await AirQualityClient().current(GHEVRA)

    assert len(rows) == 24
    assert rows[5].pm25 is None
    assert rows[5].pm10 is not None


def test_client_is_always_configured_because_the_endpoint_is_keyless() -> None:
    # Callers treat every feed uniformly; this one is never "not configured".
    assert AirQualityClient().configured is True


def test_dust_is_documented_as_not_being_fire_evidence() -> None:
    """Guard the one dangerous misuse of this feed.

    Delhi's post-monsoon dust season drives `dust` far above any plausible smoke
    contribution. A UI that rendered `dust` as fire evidence would be confidently
    wrong, so the module must keep saying so - this test fails if that warning
    is quietly deleted.
    """
    import dhuan.ingest.airquality as mod

    text = Path(mod.__file__).read_text().lower()
    assert "not a fire source" in text
    assert "must never be presented as wildfire smoke" in text
    # and it must not quietly import the fire pipeline
    assert "firms" not in text.replace("nasa\nfirms", "").replace("firms active-fire", "")


def test_observation_exposes_no_fire_field() -> None:
    """No field on the record could be mistaken for a fire detection."""
    fields = set(AirQualityObservation.__dataclass_fields__)
    assert fields == {
        "observed_at",
        "pm25",
        "pm10",
        "dust",
        "us_aqi",
        "european_aqi",
        "provider",
        "license_note",
    }


@pytest.mark.anyio
@respx.mock
async def test_upstream_error_is_not_swallowed() -> None:
    respx.get(AIR_QUALITY_URL).mock(return_value=httpx.Response(500, text="boom"))
    with pytest.raises(Exception):  # noqa: B017 - type checked by caller
        await AirQualityClient().current(GHEVRA)


def test_settings_do_not_require_a_key_for_this_feed() -> None:
    # No new credential field was added; there is nothing to configure.
    assert not hasattr(get_settings(), "air_quality_api_key")

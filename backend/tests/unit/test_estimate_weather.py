"""The estimate must carry the conditions that explain it.

A PM2.5 number does not tell a user why their street differs from the next one
over. Wind does. The estimate response now includes it so the UI can explain
the number without a second round trip.
"""

from __future__ import annotations

from dhuan.agents.corpus import _ventilation, compass
from dhuan.api.models import WeatherOut


def test_weather_out_renders_the_bearing_as_words() -> None:
    from dhuan.api.routers.estimate import _weather_out

    class W:
        wind_speed_ms = 2.5
        wind_gusts_ms = 4.0
        wind_direction_deg = 292.0
        temperature_c = 18.0
        relative_humidity_pct = 62.0
        precipitation_mm = 0.0

    class Outcome:
        age_seconds = 1800.0
        stale = False

    out = _weather_out(W(), Outcome())
    assert out is not None
    assert out.wind_from_label == "west-northwest"
    assert out.wind_speed_ms == 2.5
    assert out.wind_gust_ms == 4.0
    assert out.ventilation is not None


def test_weather_out_is_none_without_data() -> None:
    from dhuan.api.routers.estimate import _weather_out

    assert _weather_out(None, None) is None


def test_ventilation_is_derived_not_measured() -> None:
    """It is inferred from wind speed, so it must not look like a reading."""
    verdict, reason = _ventilation(0.4, None)
    assert verdict == "poor"
    assert reason  # every verdict carries its reason


def test_compass_covers_the_cardinals() -> None:
    assert compass(0.0) == "north"
    assert compass(180.0) == "south"
    assert compass(270.0) == "west"


def test_weather_out_serialises_with_its_reasons() -> None:
    out = WeatherOut(
        wind_speed_ms=3.0,
        wind_gust_ms=None,
        wind_from_deg=10.0,
        wind_from_label="north",
        temperature_c=20.0,
        relative_humidity_pct=50.0,
        precipitation_mm=0.0,
        age_seconds=60.0,
        stale=False,
        ventilation="moderate",
        ventilation_reason="there is light wind",
    )
    body = out.model_dump()
    assert body["ventilation"] == "moderate"
    assert body["ventilation_reason"] == "there is light wind"

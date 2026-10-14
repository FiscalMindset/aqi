"""GET /v1/estimate — street-level PM2.5 with an honest 80% interval.

Behaviour (decided in docs/adr/0007-model-serving.md):
  * inside Delhi-NCR coverage polygon → 422 otherwise
  * nearest-station persistence is the served median when it is the measured
    best baseline; the model serves gridded points away from stations
  * every response carries: pm25_low/mid/high, CPCB category (with the
    hourly-vs-24h caveat), nearest station reading, model version,
    data_age_seconds and a plain-language honesty note
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from dhuan.agents.corpus import _ventilation, compass
from dhuan.api.errors import outside_coverage_problem, upstream_problem
from dhuan.api.models import CrossCheckOut, EstimateOut, FeatureContribution, WeatherOut
from dhuan.api.services import nearest_reading, stations_near, weather_now
from dhuan.core.config import Settings, get_settings
from dhuan.core.logging import get_logger
from dhuan.core.metrics import record
from dhuan.core.units import Point
from dhuan.geo.boundary import point_in_ncr
from dhuan.ingest.types import utcnow
from dhuan.model.cpcb import CPCB_TABLE_VERSION, category_for_pm25
from dhuan.model.predict import (
    ModelNotTrainedError,
    build_features_for_point,
    explain_features,
    load_artifact,
    nearest_station_fallback,
    persistence_anchor,
    predict_from_frame,
    static_sources_default,
)

router = APIRouter(prefix="/v1", tags=["estimate"])

logger = get_logger("api.estimate")

def _weather_out(weather: Any, outcome: Any) -> WeatherOut | None:
    """Turn the weather observation into the block the UI renders.

    The ventilation verdict is derived from wind, so it is labelled as derived
    and carries the reason: "poor, the air is nearly still" is far more useful
    to someone deciding whether to go for a walk than a bare number.
    """
    if weather is None:
        return None
    speed = weather.wind_speed_ms
    verdict, reason = _ventilation(speed, weather.wind_gusts_ms)
    return WeatherOut(
        wind_speed_ms=round(speed, 2),
        wind_gust_ms=round(weather.wind_gusts_ms, 2) if weather.wind_gusts_ms else None,
        wind_from_deg=round(weather.wind_direction_deg, 1),
        wind_from_label=compass(weather.wind_direction_deg),
        temperature_c=round(weather.temperature_c, 1),
        relative_humidity_pct=round(weather.relative_humidity_pct, 0),
        precipitation_mm=round(weather.precipitation_mm, 1),
        age_seconds=round(outcome.age_seconds, 0),
        stale=outcome.stale,
        ventilation=verdict,
        ventilation_reason=reason,
    )

def _cross_check_out(rows: Any, our_pm25: float | None) -> CrossCheckOut | None:
    """Independent CAMS PM2.5 for the same hour, beside our estimate.

    Never merged and never presented as an attribution: a regional aerosol grid
    cannot say which source produced the pollution. It is here so a large gap
    between the two is visible rather than hidden - that gap usually means the
    local monitor is catching a pocket of pollution the grid has smoothed away.
    """
    if not rows:
        return None
    now = utcnow()
    # Pick the row closest to now rather than blindly taking the first: the
    # forecast starts at midnight, which is not "current".
    best = min(rows, key=lambda r: abs((now - r.observed_at).total_seconds()))
    delta = None
    if our_pm25 is not None and best.pm25 is not None:
        delta = round(our_pm25 - best.pm25, 1)
    return CrossCheckOut(
        pm25_ugm3=best.pm25,
        us_aqi=best.us_aqi,
        european_aqi=best.european_aqi,
        dust_ugm3=best.dust,
        delta_ugm3=delta,
        age_seconds=round(best.age_seconds(), 0),
    )


HONESTY_NOTE = (
    "Estimate, not a measurement. The interval is the model's calibrated 80% "
    "range; CPCB categories are defined on 24-hour averages and are applied "
    "here to hourly values, which is deliberately conservative."
)


@router.get(
    "/estimate",
    response_model=EstimateOut,
    summary="PM2.5 estimate with 80% interval for a point in Delhi-NCR",
    response_description="Estimate, interval, category, nearest station, freshness.",
)
async def estimate(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    explain: Annotated[
        bool,
        Query(
            description=(
                "Include the per-parameter contribution breakdown. Costs one "
                "extra batched model pass, so it is opt-in: the agent and the "
                "hot path do not need it."
            )
        ),
    ] = False,
    settings: Settings = Depends(get_settings),
) -> EstimateOut:
    return await compute_estimate(lat, lon, settings, explain=explain)


async def compute_estimate(
    lat: float, lon: float, settings: Settings, *, explain: bool = False
) -> EstimateOut:
    """The estimate pipeline, callable from routes AND agent tools."""
    point = Point(lat=lat, lon=lon)
    if not point_in_ncr(point):
        raise outside_coverage_problem(lat, lon)

    # 1) nearest station reading (anchors the estimate and is shown verbatim)
    station_outcome = await stations_near(lat, lon, settings)
    readings = station_outcome.data or []
    nearest = nearest_reading(readings, lat, lon)
    station_pm25 = nearest[0].value if nearest else None
    station_age = nearest[0].age_seconds() if nearest else None

    # 2) weather now (wind/temp/etc. explain the number and feed the cone)
    wx = await weather_now(lat, lon, settings)

    # Independent CAMS-based PM2.5 for the same point, purely as a cross-check.
    # Failures are swallowed on purpose: a missing second opinion must never
    # take down the estimate the reader actually came for.
    cross_check: list[Any] = []
    try:
        from dhuan.ingest.airquality import AirQualityClient  # noqa: PLC0415

        cross_check = await AirQualityClient(settings).current(Point(lat=lat, lon=lon))
    except Exception as exc:
        record("CrossCheckUnavailable", 1)
        logger.warning("cross_check_unavailable: %s", type(exc).__name__)
    weather = wx.data

    # 3) model or baseline
    served_by = "nearest-station"
    pm25_low = pm25_mid = pm25_high = 0.0
    model_version = settings.model_version
    features_used: list[FeatureContribution] = []
    anchor_value: float | None = station_pm25
    model_adjustment: float | None = None
    if weather is not None and station_pm25 is not None:
        try:
            artifact = load_artifact()
            sources = static_sources_default()
            features = build_features_for_point(
                lat=lat,
                lon=lon,
                ts=datetime.utcnow(),
                weather_row={
                    "wind_speed": weather.wind_speed_ms,
                    "wind_gust": weather.wind_gusts_ms or weather.wind_speed_ms * 1.4,
                    "temp_c": weather.temperature_c,
                    "rh": weather.relative_humidity_pct,
                    "precip": weather.precipitation_mm,
                    "wind_dir": weather.wind_direction_deg,
                },
                station_lag1=station_pm25,
                station_lag24=station_pm25,
                station_rolling6=station_pm25,
                station_sources=sources,
            )
            prediction = predict_from_frame(features, artifact)
            served_by = prediction.source
            pm25_low, pm25_mid, pm25_high = (
                prediction.pm25_low,
                prediction.pm25_mid,
                prediction.pm25_high,
            )
            model_version = f"pkl:{prediction.model_version}"
            anchor_value = persistence_anchor(features)
            model_adjustment = pm25_mid - anchor_value
            if explain:
                # Which parameters produced this number, for this point. One
                # batched model pass; skipped by default so the hot path and the
                # agent stay fast.
                features_used = [
                    FeatureContribution(**c) for c in explain_features(features, artifact)
                ]
        except ModelNotTrainedError:
            record("EstimateModelMissing", 1)
        except Exception:
            record("EstimateModelFailed", 1)
    if served_by != "model":
        base = nearest_station_fallback(station_pm25 or 0.0)
        pm25_low, pm25_mid, pm25_high = base.pm25_low, base.pm25_mid, base.pm25_high
        model_version = "nearest-station-baseline"
        features_used = []
        model_adjustment = 0.0
        record("EstimateServedByBaseline", 1)

    if station_pm25 is None and served_by != "model":
        # no station nearby and no model: no honest number is possible
        raise upstream_problem(
            "openaq",
            "No station reading near this point and no model artifact; refusing to invent a value.",
        )

    record("EstimatesServed", 1)
    return EstimateOut(
        lat=lat,
        lon=lon,
        ts_utc=datetime.now(UTC).isoformat(timespec="seconds"),
        pm25_low=round(pm25_low, 1),
        pm25_mid=round(pm25_mid, 1),
        pm25_high=round(pm25_high, 1),
        category=category_for_pm25(pm25_mid),
        aqi_sub_index=None,
        nearest_station_pm25=station_pm25,
        nearest_station_name=nearest[0].name if nearest else None,
        data_age_seconds=max(station_age or 0.0, wx.age_seconds),
        stale=station_outcome.stale or wx.stale,
        model_version=model_version,
        served_by=served_by,
        cpcb_table_version=CPCB_TABLE_VERSION,
        honesty=HONESTY_NOTE,
        persistence_anchor_ugm3=round(anchor_value, 1) if anchor_value is not None else None,
        model_adjustment_ugm3=round(model_adjustment, 1) if model_adjustment is not None else None,
        features_used=features_used,
        weather=_weather_out(weather, wx),
        cross_check=_cross_check_out(cross_check, pm25_mid),
        method=(
            "gradient-boosted-trees on persistence-anchored residual"
            if served_by == "model"
            else "persistence baseline (model unavailable)"
        ),
    )

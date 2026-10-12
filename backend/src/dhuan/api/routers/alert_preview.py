"""POST /v1/alerts/preview — render the alert email without sending it.

Lets a subscriber see exactly what they will receive before subscribing, and
lets us verify the template against a real estimate. The rendered HTML is
returned, not sent.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from dhuan.alerts.alerts import compose_message
from dhuan.alerts.email_template import compose_html_email
from dhuan.api.errors import outside_coverage_problem
from dhuan.api.schemas import AlertPreviewRequest, AlertPreviewResponse
from dhuan.api.services import weather_now
from dhuan.core.config import Settings, get_settings
from dhuan.core.units import Point
from dhuan.geo.boundary import point_in_ncr
from dhuan.model.predict import load_artifact

router = APIRouter(prefix="/v1", tags=["alerts"])


def _station_id(name: str | None) -> int | None:
    """OpenAQ location id from a station label like "New Delhi-8118"."""
    if not name:
        return None
    tail = name.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else None


@router.post(
    "/alerts/preview",
    summary="Render the alert email for a point (no email is sent)",
    response_description="Subject, plain-text body and responsive HTML.",
)
async def preview_alert(
    body: AlertPreviewRequest,
    settings: Settings = Depends(get_settings),
) -> AlertPreviewResponse:
    point = Point(lat=body.lat, lon=body.lon)
    if not point_in_ncr(point):
        raise outside_coverage_problem(body.lat, body.lon)

    from dhuan.api.routers.estimate import compute_estimate

    est = await compute_estimate(body.lat, body.lon, settings)

    weather: dict[str, Any] = {}
    wx = await weather_now(body.lat, body.lon, settings)
    if wx.data is not None:
        w = wx.data
        weather = {
            "temperature_c": w.temperature_c,
            "humidity_pct": w.relative_humidity_pct,
            "wind_speed_ms": w.wind_speed_ms,
            "wind_direction_deg": w.wind_direction_deg,
            "pressure_hpa": getattr(w, "pressure_hpa", None),
            "precipitation_mm": w.precipitation_mm,
            "observed_at": getattr(w, "observed_at", None),
        }

    accuracy: dict[str, float] | None = None
    try:
        from dhuan.api.routers.model_card import _load

        accuracy = {"mae": float(_load()["temporal_holdout"]["mae"])}
    except Exception:
        accuracy = None

    version = est.model_version
    try:
        load_artifact()
        version = "gbt-anchored"
    except Exception:
        version = "persistence-baseline"

    # In production this is the subscription's own unsubscribe token; the
    # preview uses a placeholder so the rendered link is visible but inert.
    token = body.unsubscribe_token or ""

    subject, plain = compose_message(
        locality=body.locality or "your locality",
        pm25_mid=est.pm25_mid,
        pm25_low=est.pm25_low,
        pm25_high=est.pm25_high,
        category=est.category,
        likely_category=None,
        unsubscribe_url=settings.public_web_url or "/",
    )
    html = compose_html_email(
        locality=body.locality or "your locality",
        pm25_mid=est.pm25_mid,
        pm25_low=est.pm25_low,
        pm25_high=est.pm25_high,
        category=est.category,
        threshold_category=body.threshold_category or "Poor",
        served_by=est.served_by,
        model_version=version,
        persistence_anchor=est.persistence_anchor_ugm3,
        model_adjustment=est.model_adjustment_ugm3,
        features=[f.model_dump() for f in est.features_used],
        station_name=est.nearest_station_name,
        station_id=_station_id(est.nearest_station_name),
        station_age_hours=(est.data_age_seconds / 3600.0) if est.data_age_seconds else None,
        weather=weather,
        causes=body.causes or None,
        advice=body.advice,
        unsubscribe_url=(
            f"{settings.public_web_url.rstrip('/')}/v1/subscriptions/unsubscribe?token={token}"
            if token
            else (settings.public_web_url or "/")
        ),
        web_url=settings.public_web_url or "",
        model_accuracy=accuracy,
    )
    return AlertPreviewResponse(subject=subject, body=plain, html=html)

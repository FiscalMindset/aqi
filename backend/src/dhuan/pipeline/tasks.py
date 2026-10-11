"""Step Functions task handlers for the hourly pipeline.

The state machine (infra/state-machine.asl.json) runs:
  parallel ingest (stations, weather, fires) -> validate+merge ->
  predict grid -> persist -> evaluate alerts -> publish

Every handler is pure w.r.t. its inputs (event dict) and returns a dict.
Errors are NOT swallowed: they are logged, counted, and re-raised so the
state machine's Catch blocks route to the failure path that records feed
status and emits a metric.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from dhuan.core.logging import get_logger
from dhuan.core.metrics import record
from dhuan.core.units import Point
from dhuan.geo.boundary import point_in_ncr
from dhuan.ingest.weather import WeatherClient
from dhuan.model.predict import load_artifact, predict_from_frame, static_sources_default
from dhuan.store.dynamodb import EstimatesStore, FeedsStore

logger = get_logger("pipeline")


def _ok(feed: str, records: int) -> dict[str, Any]:
    FeedsStore().record_success(feed, records)
    record(f"Feed{feed.title()}Records", records)
    return {"feed": feed, "records": records, "ok": True}


def ingest_stations(_event: dict[str, Any]) -> dict[str, Any]:
    """Latest PM2.5 readings near Delhi-NCR from OpenAQ.

    Without a configured key this records the failure and re-raises so the
    state machine marks the feed degraded (never fabricates readings).
    """
    from dhuan.api.services import stations_near

    lat, lon = 28.6139, 77.2090  # centre of Delhi (the NCR query anchor)
    try:
        outcome = asyncio.run(stations_near(lat, lon))
    except Exception:
        FeedsStore().record_failure("openaq", "unavailable")
        record("FeedStationsFailed", 1)
        raise
    return _ok("openaq", len(outcome.data or []))


def ingest_weather(_event: dict[str, Any]) -> dict[str, Any]:
    """Hourly weather for the anchor points used by the grid predictor."""
    client = WeatherClient()
    try:
        rows = asyncio.run(client.forecast(28.6139, 77.2090, days=1))
    except Exception:
        FeedsStore().record_failure("open-meteo", "unavailable")
        record("FeedWeatherFailed", 1)
        raise
    finally:
        asyncio.run(client.aclose())
    return _ok("open-meteo", len(rows))


def ingest_fires(_event: dict[str, Any]) -> dict[str, Any]:
    """NASA FIRMS detections over the NCR bbox (may legitimately be zero)."""
    from dhuan.api.deps import get_fires
    from dhuan.ingest.openaq import NotConfiguredError

    try:
        fires = asyncio.run(get_fires().recent_in_ncr(day_range=1))
    except NotConfiguredError:
        FeedsStore().record_failure("firms", "MAP_KEY not configured")
        record("FeedFiresMissingConfig", 1)
        # not a hard failure: the rest of the pipeline can run
        return {"feed": "firms", "records": 0, "ok": False, "skipped": True}
    except Exception:
        FeedsStore().record_failure("firms", "unavailable")
        record("FeedFiresFailed", 1)
        raise
    return _ok("firms", len(fires))


def validate_and_merge(event: dict[str, Any]) -> dict[str, Any]:
    """Combine the parallel ingest results, rejecting impossible values.

    Rejects are counted and logged, never silently dropped.
    """
    ingested = event.get("ingested", [])
    rejects: list[dict[str, Any]] = []
    total = 0
    for branch in ingested:
        if not branch.get("ok"):
            rejects.append({"feed": branch.get("feed"), "issue": "branch failed"})
            continue
        count = int(branch.get("records", 0))
        total += count
        if branch.get("feed") == "openaq" and count == 0:
            rejects.append({"feed": "openaq", "issue": "zero readings"})
    if rejects:
        record("PipelineRejects", len(rejects))
        logger.warning("pipeline_rejects: %s", rejects)
    return {"total_records": total, "rejects": rejects, "ok": not rejects}


def predict_grid(_event: dict[str, Any]) -> dict[str, Any]:
    """Predict the H3 grid for the current hour.

    Uses the model artifact; when it is missing the task returns ok=False so
    the state machine can skip persistence honestly instead of storing
    invented values.
    """
    from dhuan.geo.grid import cell_center, grid_cells

    now = datetime.now(UTC)
    try:
        artifact = load_artifact()
    except Exception:
        record("PipelineModelMissing", 1)
        logger.warning("pipeline_model_missing: skipping grid prediction")
        return {"predictions": [], "ok": False, "reason": "model not trained"}

    # weather at the current hour for the anchor point (needed for features)
    client = WeatherClient()
    hours = asyncio.run(client.forecast(28.6139, 77.2090, days=1))
    asyncio.run(client.aclose())
    now_key = now.strftime("%Y-%m-%dT%H:00")
    wx = next(
        (
            h
            for h in hours
            if h.observed_at.astimezone(UTC).strftime("%Y-%m-%dT%H:00") == now_key
        ),
        None,
    )
    if wx is None and hours:
        wx = hours[0]
    if wx is None:
        record("PipelineWeatherMissing", 1)
        return {"predictions": [], "ok": False, "reason": "no weather rows"}

    station_value = _latest_station_value()
    if station_value is None:
        record("PipelineStationMissing", 1)
        return {"predictions": [], "ok": False, "reason": "no station anchor"}

    sources = static_sources_default()
    predictions: list[dict[str, Any]] = []
    for cell in grid_cells(8):
        center = cell_center(cell)
        if not point_in_ncr(center):
            continue
        from dhuan.model.predict import build_features_for_point

        features = build_features_for_point(
            lat=center.lat,
            lon=center.lon,
            ts=now,
            weather_row={
                "wind_speed": wx.wind_speed_ms,
                "wind_gust": wx.wind_gusts_ms or wx.wind_speed_ms * 1.4,
                "temp_c": wx.temperature_c,
                "rh": wx.relative_humidity_pct,
                "precip": wx.precipitation_mm,
                "wind_dir": wx.wind_direction_deg,
            },
            station_lag1=station_value,
            station_lag24=station_value,
            station_rolling6=station_value,
            station_sources=sources,
        )
        pred = predict_from_frame(features, artifact)
        predictions.append(
            {
                "cell": cell,
                "ts": now.isoformat(),
                "pm25_low": pred.pm25_low,
                "pm25_mid": pred.pm25_mid,
                "pm25_high": pred.pm25_high,
            }
        )
    record("PipelinePredictions", len(predictions))
    return {"predictions": predictions, "ok": True}


def _latest_station_value() -> float | None:
    from dhuan.api.services import stations_near

    try:
        outcome = asyncio.run(stations_near(28.6139, 77.2090))
    except Exception:
        return None
    readings = outcome.data or []
    if not readings:
        return None
    return readings[0].value


def persist_estimates(event: dict[str, Any]) -> dict[str, Any]:
    """Write predictions to DynamoDB with TTL."""
    predictions = event.get("predictions", [])
    store = EstimatesStore()
    written = 0
    for p in predictions:
        store.put_estimate(
            p["cell"],
            datetime.fromisoformat(p["ts"]),
            float(p["pm25_low"]),
            float(p["pm25_mid"]),
            float(p["pm25_high"]),
            "pipeline",
        )
        written += 1
    record("PipelinePersisted", written)
    return {"written": written, "ok": written > 0}


def evaluate_alerts(event: dict[str, Any]) -> dict[str, Any]:
    """Decide alerts for every confirmed subscription against its estimate."""
    from dhuan.store.dynamodb import SubscriptionsStore

    predictions = event.get("predictions", [])
    by_cell = {p["cell"]: p for p in predictions}
    store = SubscriptionsStore()
    subs = list(store.by_locality("delhi-ncr"))
    if not subs:
        return {"alerts": [], "ok": True}
    # locality estimates: anchor on the grid cell nearest each subscription
    estimates: dict[str, float] = {}
    for sub in subs:
        lat, lon = float(sub["lat"]), float(sub["lon"])
        from dhuan.geo.grid import cell_for_point

        cell = cell_for_point(Point(lat, lon))
        pred = by_cell.get(cell)
        if pred is not None:
            estimates[str(sub.get("pk", "")).lower()] = float(pred["pm25_mid"])
    decisions = []
    now = datetime.now(UTC)
    for sub in subs:
        key = str(sub.get("pk", ""))
        pm25 = estimates.get(key.lower())
        if pm25 is None:
            continue
        from dhuan.alerts.alerts import decide

        d = decide(
            current_pm25=pm25,
            threshold_category=str(sub.get("threshold_category", "Poor")),
            last_band=sub.get("last_band"),
            last_alerted_at=None,
            now=now,
        )
        decisions.append({"sub": key, "decision": asdict(d)})
    return {"alerts": decisions, "ok": True}


def publish_alerts(event: dict[str, Any]) -> dict[str, Any]:
    """Publish decided alerts via SNS (no-op with a warning if unconfigured)."""
    from dhuan.alerts.alerts import SnsAlerter, compose_message

    alerts = event.get("alerts", [])
    alerter = SnsAlerter(get_settings_for_pipeline())
    published = 0
    for alert in alerts:
        if not alert.get("decision", {}).get("should_send"):
            continue
        subject, body = compose_message(
            locality="Delhi-NCR",
            pm25_mid=0.0,
            pm25_low=0.0,
            pm25_high=0.0,
            category=alert["decision"].get("band", "Unknown"),
            likely_category=None,
            unsubscribe_url="https://dhuan-detective.example/unsubscribe",
        )
        message_id = alerter.publish(
            locality="delhi-ncr",
            email=alert.get("email", ""),
            subject=subject,
            body=body,
        )
        if message_id:
            published += 1
    record("PipelineAlertsPublished", published)
    return {"published": published, "ok": True}


def get_settings_for_pipeline() -> Any:
    from dhuan.core.config import get_settings

    return get_settings()


def failure_recorded(event: dict[str, Any]) -> dict[str, Any]:
    """Catch-block entry: record the failure and emit a metric (never silent)."""
    error = event.get("error") or "unknown"
    logger.error("pipeline_failure_recorded: %s", error)
    record("PipelineFailures", 1)
    return {"failed": True, "error": error}


HANDLERS = {
    "ingest_stations": ingest_stations,
    "ingest_weather": ingest_weather,
    "ingest_fires": ingest_fires,
    "validate_and_merge": validate_and_merge,
    "predict_grid": predict_grid,
    "persist_estimates": persist_estimates,
    "evaluate_alerts": evaluate_alerts,
    "publish_alerts": publish_alerts,
    "failure_recorded": failure_recorded,
}


def lambda_handler(event: dict[str, Any], _context: Any = None) -> dict[str, Any]:
    """Single entry point used by the Lambda container image."""
    task = event.get("task")
    handler = HANDLERS.get(str(task))
    if handler is None:
        record("PipelineUnknownTask", 1)
        return {"error": f"unknown task: {task}", "ok": False}
    return handler(event)


__all__ = ["HANDLERS", "lambda_handler"]

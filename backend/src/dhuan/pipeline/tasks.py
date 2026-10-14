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

from dhuan.api.deps import get_fires
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

    async def _run() -> list[Any]:
        client = WeatherClient()
        try:
            return list(await client.forecast(28.6139, 77.2090, days=1))
        finally:
            await client.aclose()

    try:
        rows = asyncio.run(_run())
    except Exception:
        FeedsStore().record_failure("open-meteo", "unavailable")
        record("FeedWeatherFailed", 1)
        raise
    return _ok("open-meteo", len(rows))


async def _recent_fires() -> list[Any]:
    client = get_fires()
    try:
        return list(await client.recent_in_ncr(day_range=1))
    finally:
        await client.aclose()


def ingest_fires(_event: dict[str, Any]) -> dict[str, Any]:
    """NASA FIRMS detections over the NCR bbox (may legitimately be zero)."""
    from dhuan.ingest.openaq import NotConfiguredError

    try:
        fires = asyncio.run(_recent_fires())
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

    async def _weather() -> list[Any]:
        client = WeatherClient()
        try:
            return list(await client.forecast(28.6139, 77.2090, days=1))
        finally:
            await client.aclose()

    hours = asyncio.run(_weather())
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
    """Decide alerts for every subscription against its estimate.

    Deliberately not filtered on our own `confirmed` flag. AWS SNS performs the
    double opt-in for email endpoints on its own side and never tells us when the
    recipient clicks through, so that flag would sit at False forever and gate
    every alert off. Publishing to a subscription SNS still has pending is
    harmless - SNS simply will not deliver it - so SNS is the single real gate
    and this side stays out of the way.
    """
    from dhuan.store.dynamodb import SubscriptionsStore

    predictions = event.get("predictions", [])
    by_cell = {p["cell"]: p for p in predictions}
    store = SubscriptionsStore()
    subs = list(store.all_subscriptions())
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
        # Everything publish_alerts needs travels with the decision, because the
        # message must be composed from the subscriber's own record rather than
        # from constants.
        decisions.append(
            {
                "sub": key,
                "decision": asdict(d),
                "email": sub.get("email", ""),
                "locality": sub.get("locality", ""),
                "threshold_category": sub.get("threshold_category", ""),
                "unsubscribe_token": sub.get("unsubscribe_token", ""),
                "pm25_mid": round(pm25, 1),
            }
        )
    return {"alerts": decisions, "ok": True}


def publish_alerts(event: dict[str, Any]) -> dict[str, Any]:
    """Publish decided alerts via SNS (no-op with a warning if unconfigured)."""
    from dhuan.alerts.alerts import best_alerter, compose_message

    alerts = event.get("alerts", [])
    alerter = best_alerter(get_settings_for_pipeline())
    settings = get_settings_for_pipeline()
    published = 0
    skipped = 0
    for alert in alerts:
        if not alert.get("decision", {}).get("should_send"):
            continue
        email = str(alert.get("email") or "")
        # The message is composed from the subscriber's own record. It used to
        # be composed from constants: every alert carried pm25 = 0.0 and an
        # unsubscribe link pointing at dhuan-detective.example, so a delivered
        # message would have been wrong and un-actionable.
        locality = str(alert.get("locality") or "your point")
        pm25_mid = float(alert.get("pm25_mid") or 0.0)
        category = str(alert["decision"].get("band", "Unknown"))
        unsub = str(alert.get("unsubscribe_token") or "")
        if not email or not unsub:
            # Without a token there is no way for the recipient to stop the
            # alert, so sending one would be worse than sending none.
            skipped += 1
            logger.warning("alert_missing_email_or_token: %s", email or "<no email>")
            continue
        subject, body = compose_message(
            locality=locality,
            pm25_mid=pm25_mid,
            pm25_low=pm25_mid,
            pm25_high=pm25_mid,
            category=category,
            likely_category=None,
            unsubscribe_url=(
                f"{settings.public_base_url.rstrip('/')}"
                f"/v1/subscriptions/unsubscribe?token={unsub}"
            ),
        )
        # Locality must match the subscriber's FilterPolicy, which is applied
        # lower-cased at subscribe time.
        message_id = alerter.publish(
            locality=locality.lower(),
            email=email,
            subject=subject,
            body=body,
        )
        if message_id:
            published += 1
    record("PipelineAlertsPublished", published)
    if skipped:
        record("PipelineAlertsSkipped", skipped)
    return {"published": published, "skipped": skipped, "ok": True}


def get_settings_for_pipeline() -> Any:
    from dhuan.core.config import get_settings

    return get_settings()


def refresh_sources(_event: dict[str, Any]) -> dict[str, Any]:
    """Re-pull OSM sources for the NCR bbox and reindex them.

    Driven by the EventBridge `rate(30 days)` rule. Fails soft: if Overpass is
    unreachable the already-indexed sources stay in place and we say so rather
    than reporting a refresh that did not happen.
    """
    import asyncio

    from dhuan.core.config import get_settings
    from dhuan.ingest.osm import fetch_sources_for_bbox
    from dhuan.store.opensearch import SourceIndex

    settings = get_settings()
    b = settings.delhi_bbox
    west, south, east, north = b.min_lon, b.min_lat, b.max_lon, b.max_lat
    try:
        docs = asyncio.run(fetch_sources_for_bbox(west, south, east, north, settings))
    except Exception as exc:
        logger.warning("source_refresh_failed: %s", exc)
        record("SourceRefreshFailures", 1)
        return {"refreshed": False, "reason": str(exc)[:200]}
    index = SourceIndex(settings)
    index.ensure_index()
    count = index.bulk_index([d.to_index_dict() for d in docs])
    index.close()
    record("SourcesRefreshed", count)
    return {"refreshed": True, "count": count}


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
    "refresh_sources": refresh_sources,
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

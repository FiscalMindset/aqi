"""GET /v1/status — per-feed freshness, pipeline state, versions.

Reads feed records from DynamoDB; when the store is unreachable the route
reports the feed as unknown rather than pretending freshness. This is the
honest-status page backing the /status frontend route.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast

from fastapi import APIRouter, Depends

from dhuan.api.deps import get_feeds_store
from dhuan.api.models import FeedStatusOut, StatusOut
from dhuan.core.config import Settings, get_settings
from dhuan.geo.boundary import bbox_of_ncr, provenance

router = APIRouter(prefix="/v1", tags=["status"])


@router.get(
    "/status",
    response_model=StatusOut,
    summary="System status: feed freshness, versions, coverage",
    response_description="Feed records, model/API versions and coverage bounds.",
)
async def status(settings: Settings = Depends(get_settings)) -> StatusOut:
    feeds: list[FeedStatusOut] = []
    try:
        records = get_feeds_store(settings).all()
    except Exception as exc:
        records = []
        feeds = []
        # surfaced as a synthetic unknown feed so the UI can show it
        feeds = [
            FeedStatusOut(
                feed="dynamodb", ok=False, last_success_at=None, age_seconds=None,
                last_error=str(exc)[:200],
            )
        ]
    else:
        for f in records:
            age = f.age_seconds()
            feeds.append(
                FeedStatusOut(
                    feed=f.feed,
                    ok=f.ok,
                    last_success_at=f.last_success_at.isoformat() if f.last_success_at else None,
                    age_seconds=round(age, 1) if age is not None else None,
                    last_error=f.last_error,
                    records_last_run=f.records_last_run,
                )
            )
    min_lat, min_lon, max_lat, max_lon = bbox_of_ncr()
    prov = provenance()
    real_feeds = [f for f in feeds if f.feed != "dynamodb"]
    status_value = "ok" if real_feeds and all(f.ok for f in real_feeds) else "degraded"
    return StatusOut(
        status=cast("Literal['ok', 'degraded']", status_value),
        api_version=settings.api_version,
        model_version=settings.model_version,
        feeds=feeds,
        coverage={
            "bbox": {
                "min_lat": min_lat,
                "min_lon": min_lon,
                "max_lat": max_lat,
                "max_lon": max_lon,
            },
            "boundary_source": prov.get("source", "unknown"),
            "boundary_fetched": prov.get("fetched_utc", "unknown"),
            "boundary_license": prov.get("license", "unknown"),
        },
        demo_mode=settings.demo_mode,
    )


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")

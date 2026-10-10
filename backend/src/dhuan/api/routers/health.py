"""Health and readiness routes.

/health is liveness (always fast, no I/O). /ready checks the real
dependencies: DynamoDB tables, OpenSearch index and feed freshness, and
reports a per-component breakdown so the frontend /status page and load
balancers can react precisely.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from dhuan.api.deps import get_feeds_store, get_source_index
from dhuan.api.models import HealthOut, ReadyCheck, ReadyOut
from dhuan.core.config import Settings, get_settings
from dhuan.core.logging import get_logger

logger = get_logger("api.health")
router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthOut,
    summary="Liveness probe",
    response_description="Service is alive.",
)
async def health(settings: Settings = Depends(get_settings)) -> HealthOut:
    return HealthOut(status="ok", version=settings.api_version, demo_mode=settings.demo_mode)


def _check_dynamodb(settings: Settings) -> ReadyCheck:
    from dhuan.store.dynamodb import dynamodb_client  # noqa: PLC0415 - probe on demand

    try:
        client = dynamodb_client(settings)
        tables = client.list_tables().get("TableNames", [])
        expected = {
            settings.dynamodb_table_estimates,
            settings.dynamodb_table_feeds,
            settings.dynamodb_table_subscriptions,
        }
        missing = expected - set(tables)
        return ReadyCheck(
            component="dynamodb",
            ok=not missing,
            detail="all tables present" if not missing else f"missing tables: {sorted(missing)}",
        )
    except Exception as exc:
        return ReadyCheck(component="dynamodb", ok=False, detail=str(exc)[:200])


def _check_opensearch(settings: Settings) -> ReadyCheck:
    try:
        index = get_source_index(settings)
        count = index.count()
        return ReadyCheck(component="opensearch", ok=count > 0, detail=f"{count} sources indexed")
    except Exception as exc:
        return ReadyCheck(component="opensearch", ok=False, detail=str(exc)[:200])


def _check_feeds(settings: Settings) -> ReadyCheck:
    try:
        store = get_feeds_store(settings)
        feeds = store.all()
        if not feeds:
            return ReadyCheck(component="feeds", ok=False, detail="no feed status recorded yet")
        stale = [
            f.feed
            for f in feeds
            if f.age_seconds() is None or (f.age_seconds() or 0) > 6 * 3600
        ]
        return ReadyCheck(
            component="feeds",
            ok=not stale,
            detail="fresh" if not stale else f"stale: {stale}",
        )
    except Exception as exc:
        return ReadyCheck(component="feeds", ok=False, detail=str(exc)[:200])


@router.get(
    "/ready",
    response_model=ReadyOut,
    summary="Readiness probe",
    response_description="Per-component readiness breakdown.",
)
async def ready(settings: Settings = Depends(get_settings)) -> ReadyOut | JSONResponse:
    checks = [
        _check_dynamodb(settings),
        _check_opensearch(settings),
        _check_feeds(settings),
    ]
    ok = all(c.ok for c in checks)
    out = ReadyOut(
        status="ready" if ok else "degraded", checks=checks, demo_mode=settings.demo_mode
    )
    return out if ok else JSONResponse(out.model_dump(), status_code=503)

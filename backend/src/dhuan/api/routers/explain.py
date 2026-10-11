"""POST /v1/explain — run the attribution + advisory agents.

Stricter rate limit than other routes (per-IP throttle in middleware config
and usage plan). Returns ranked likely causes with evidence ids, persona
advice, the full tool-call trace for the UI, and confidence.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from dhuan.agents.attribution import explain
from dhuan.api.schemas import ExplainRequest
from dhuan.core.config import Settings, get_settings

router = APIRouter(prefix="/v1", tags=["explain"])


@router.post(
    "/explain",
    summary="Explain the air at a point: likely causes with visible evidence",
    response_description="Attribution result, persona advice, tool-call trace.",
)
async def explain_route(
    body: ExplainRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    result, advice, served_by = await explain(body.lat, body.lon, settings)
    return {
        "lat": body.lat,
        "lon": body.lon,
        "served_by": served_by,
        "attribution": result.model_dump(),
        "advice": [a.model_dump() for a in advice],
        "demo_mode": settings.demo_mode,
        "note": (
            "This is an AI explanation with visible evidence. Claims are "
            "labelled 'likely'; verify with official CPCB stations."
        ),
    }

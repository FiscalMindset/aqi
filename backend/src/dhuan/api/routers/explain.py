"""POST /v1/explain — attribution, a cited explanation, and persona advice.

The cited explanation is composed from the same evidence the attribution used,
with no LLM in the loop, so it is available even when Bedrock is unreachable. If
Bedrock *is* configured, it contributes the structured attribution; the prose is
still composed from retrieved passages so every sentence stays traceable.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from dhuan.agents.attribution import explain_full
from dhuan.api.schemas import ExplainRequest
from dhuan.core.config import Settings, get_settings

router = APIRouter(prefix="/v1", tags=["explain"])


@router.post(
    "/explain",
    summary="Explain the air at a point with visible, cited evidence",
    response_description=(
        "Attribution result, a citation-grounded explanation, persona advice, "
        "the retrieval trace, and any evidence gaps."
    ),
)
async def explain_route(
    body: ExplainRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    bundle = await explain_full(body.lat, body.lon, settings)
    grounded = bundle.grounded.to_dict()
    return {
        "lat": body.lat,
        "lon": body.lon,
        "served_by": bundle.served_by,
        "attribution": bundle.result.model_dump(),
        # the headline and body are the user-facing answer; every paragraph
        # carries the passage ids it came from so the UI can show its workings
        "headline": grounded["headline"],
        "explanation": grounded["body"],
        "paragraphs": grounded["paragraphs"],
        "passages": grounded["passages"],
        "retrieval_trace": grounded["retrieval_trace"],
        "evidence_gaps": bundle.gaps,
        "advice": [a.model_dump() for a in bundle.advice],
        "demo_mode": settings.demo_mode,
        "note": (
            "The explanation is composed from retrieved evidence, not generated "
            "freely: each paragraph lists the passages it came from. Claims are "
            "hedged; verify with official CPCB stations."
        ),
    }

"""Subscription routes: create (idempotent), confirm, delete.

Each subscription stores only what the feature needs: email, locality name,
lat/lon (for the locality estimate), threshold category, and alert-state
columns for hysteresis. SNS email confirmation is used; SMS is behind the
SMS_ENABLED flag (India requires DLT sender registration — documented).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from html import escape
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from dhuan.api.errors import (
    Problem,
    ProblemType,
    not_found_problem,
    upstream_problem,
)
from dhuan.api.schemas import SubscriptionRequest
from dhuan.core.config import Settings, get_settings
from dhuan.core.logging import get_logger
from dhuan.core.metrics import record
from dhuan.core.units import Point
from dhuan.geo.boundary import point_in_ncr
from dhuan.model.cpcb import CATEGORIES
from dhuan.store.dynamodb import SubscriptionsStore

logger = get_logger("api.subscriptions")


def _store_unavailable(exc: Exception) -> Problem:
    """Store failure becomes a typed 503, never an unhandled 500."""
    logger.warning("subscription_store_unavailable: %s", exc)
    from dhuan.core.metrics import record  # noqa: PLC0415

    record("SubscriptionsStoreUnavailable", 1)
    return upstream_problem(
        "dynamodb",
        "The subscription store is unavailable; try again shortly.",
    )


router = APIRouter(prefix="/v1", tags=["subscriptions"])


@router.post(
    "/subscriptions",
    summary="Subscribe to air-quality alerts for a locality",
    status_code=201,
    response_description="Created (or already existing) subscription id.",
)
async def create_subscription(
    body: SubscriptionRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    point = Point(lat=body.lat, lon=body.lon)
    if not point_in_ncr(point):
        raise Problem(
            problem_type=ProblemType.OUTSIDE_COVERAGE,
            title="Point outside coverage",
            status=422,
            detail="Alerts are available for Delhi-NCR only.",
        )
    if body.threshold_category not in CATEGORIES:
        raise Problem(
            problem_type=ProblemType.VALIDATION,
            title="Invalid threshold",
            status=422,
            detail=f"threshold_category must be one of {list(CATEGORIES)}",
        )
    token = uuid4().hex[:16]
    unsubscribe_token = uuid4().hex[:24]
    store = SubscriptionsStore(settings)
    try:
        sub_id = store.make_id(body.email, body.locality)
        existing = store.get(sub_id)
    except Exception as exc:
        raise _store_unavailable(exc) from exc
    if existing is not None:
        record("SubscriptionIdempotentHit", 1)
        status = "already_subscribed" if existing.get("confirmed") else "pending_confirmation"
        return {
            "id": sub_id,
            "status": status,
            "locality": existing.get("locality"),
        }
    try:
        store.create(
            email=body.email,
            locality=body.locality,
            lat=body.lat,
            lon=body.lon,
            threshold_category=body.threshold_category,
            pending_token=token,
        unsubscribe_token=unsubscribe_token,
        )
    except Exception as exc:
        raise _store_unavailable(exc) from exc
    _request_sns_confirmation(settings, body.email, body.locality, token)
    record("SubscriptionsCreated", 1)
    return {
        "id": sub_id,
        "status": "pending_confirmation",
        "locality": body.locality,
        "threshold_category": body.threshold_category,
        "confirmation": (
            "A confirmation email has been sent; alerts activate after confirmation."
        ),
    }


@router.get(
    "/subscriptions/confirm",
    summary="Confirm a subscription from the email link",
)
async def confirm_subscription(
    id: Annotated[str, Query(min_length=4)],
    token: Annotated[str, Query(min_length=4)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    store = SubscriptionsStore(settings)
    try:
        existing = store.get(id)
    except Exception as exc:
        raise _store_unavailable(exc) from exc
    if existing is None:
        raise not_found_problem("Subscription")
    if existing.get("pending_token") != token:
        raise Problem(
            problem_type=ProblemType.UNAUTHORIZED,
            title="Invalid confirmation token",
            status=401,
            detail="The confirmation link is invalid or expired.",
        )
    store.confirm(id)
    record("SubscriptionsConfirmed", 1)
    return {"id": id, "status": "confirmed", "locality": existing.get("locality")}


@router.get(
    "/subscriptions/unsubscribe",
    summary="One-click unsubscribe from an alert email link",
    response_description="A confirmation page; nothing is emailed.",
)
async def unsubscribe_by_token(
    token: Annotated[str, Query(min_length=8)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    """Unsubscribe by clicking the link at the bottom of an alert.

    A GET is deliberate: mail clients and webmail scanners follow links without
    a session, and a confirmation click is already the user's intent.
    """
    store = SubscriptionsStore(settings)
    existing = store.get_by_unsubscribe_token(token)
    ok = False
    locality = ""
    if existing is not None:
        sub_id = str(existing["pk"]).removeprefix("sub#")
        locality = str(existing.get("locality", ""))
        store.delete(sub_id)
        _sns_unsubscribe(settings, str(existing.get("email", "")))
        record("SubscriptionsDeleted", 1)
        ok = True
    return HTMLResponse(_unsubscribe_page(ok, locality), status_code=200)


def _unsubscribe_page(ok: bool, locality: str) -> str:
    head = "You are unsubscribed" if ok else "That link did not match a subscription"
    detail = (
        f"No more alerts for {escape(locality)}."
        if ok and locality
        else ("The link may have been used already." if not ok else "No more alerts.")
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{head}</title></head>
<body style="margin:0;padding:40px 16px;background:#f1f5f9;font-family:-apple-system,
BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<div style="max-width:460px;margin:0 auto;background:#fff;border-radius:14px;padding:28px;">
<h1 style="margin:0 0 8px;font-size:20px;color:#0f172a;">{head}</h1>
<p style="margin:0 0 20px;font-size:14px;color:#475569;">{detail}</p>
<a href="/" style="display:inline-block;padding:10px 18px;background:#059669;color:#fff;
text-decoration:none;border-radius:8px;font-size:14px;font-weight:600;">Back to Dhuan Detective</a>
</div></body></html>"""


@router.delete(
    "/subscriptions/{id}",
    summary="Unsubscribe (immediate, no confirmation email needed)",
)
async def delete_subscription(
    id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    store = SubscriptionsStore(settings)
    try:
        existing = store.get(id)
    except Exception as exc:
        raise _store_unavailable(exc) from exc
    if existing is None:
        raise not_found_problem("Subscription")
    try:
        store.delete(id)
    except Exception as exc:
        raise _store_unavailable(exc) from exc
    # unsubscribe the email from SNS so no further messages are attempted
    _sns_unsubscribe(settings, str(existing.get("email", "")))
    record("SubscriptionsDeleted", 1)
    return {"id": id, "status": "unsubscribed", "deleted_at": datetime.now(UTC).isoformat()}


def _request_sns_confirmation(
    settings: Settings, email: str, locality: str, token: str
) -> None:
    """Subscribe the email to the SNS topic (email confirmation is SNS's job)."""
    if not settings.sns_topic_arn:
        logger.warning("sns_not_configured: subscription stored, confirmation email not sent")
        return
    from dhuan.alerts.alerts import SnsAlerter  # noqa: PLC0415 - only on create

    del token  # the confirmation link is verified against the stored token
    alerter = SnsAlerter(settings)
    try:
        alerter.sns.subscribe(
            TopicArn=settings.sns_topic_arn,
            Protocol="email",
            Endpoint=email,
            ReturnSubscriptionArn=True,
            Attributes={
                "FilterPolicy": json.dumps({"locality": [locality.lower()]})
            },
        )
    except Exception as exc:
        logger.warning("sns_subscribe_failed: %s", exc)


def _sns_unsubscribe(settings: Settings, email: str) -> None:
    if not settings.sns_topic_arn:
        return
    from dhuan.alerts.alerts import SnsAlerter  # noqa: PLC0415 - only on delete

    alerter = SnsAlerter(settings)
    try:
        resp = alerter.sns.list_subscriptions_by_topic(TopicArn=settings.sns_topic_arn)
        for sub in resp.get("Subscriptions", []):
            arn = sub.get("SubscriptionArn")
            if sub.get("Endpoint") == email and arn and arn != "PendingConfirmation":
                alerter.sns.unsubscribe(SubscriptionArn=arn)
    except Exception as exc:
        logger.warning("sns_unsubscribe_failed: %s", exc)

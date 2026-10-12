"""Request bodies for POST routes (kept out of models.py: bodies vs responses)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class SubscriptionRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    locality: str = Field(min_length=2, max_length=120)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    threshold_category: str = Field("Poor")


class AlertPreviewRequest(BaseModel):
    """Render the alert email for a point without sending anything."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    locality: str = Field(default="", max_length=120)
    threshold_category: str = Field(default="Poor", max_length=32)
    causes: list[str] = Field(default_factory=list, max_length=8)
    advice: str | None = Field(default=None, max_length=400)
    unsubscribe_token: str = Field(default="", max_length=64)


class AlertPreviewResponse(BaseModel):
    subject: str
    body: str
    html: str

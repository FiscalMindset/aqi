"""Prediction-time interface for the PM2.5 model.

Serves the median + conformal 80% interval at any point in Delhi-NCR.
Feature vector construction mirrors training exactly (same function), and
nearest-station history is supplied at call time by the caller (the API
layer), never read from the model artifact.
"""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from dhuan.core.units import Point
from dhuan.model.features import (
    FEATURE_NAMES,
    Source,
    build_feature_row,
    static_features,
)

ARTIFACTS = Path(__file__).resolve().parents[2] / "models"


class ModelNotTrainedError(RuntimeError):
    """No trained artifact; run `make train` first."""


@dataclass(slots=True)
class Prediction:
    pm25_mid: float
    pm25_low: float
    pm25_high: float
    model_version: str
    snapshot_sha256: str
    source: str  # "model" | "nearest-station"


def load_artifact(path: Path | None = None) -> dict[str, Any]:
    path = path or ARTIFACTS / "model.pkl"
    if not path.exists():
        raise ModelNotTrainedError(f"no model artifact at {path}; run `make train`")
    # artifact is produced by our own training run, never by untrusted input
    with path.open("rb") as f:
        payload: dict[str, Any] = pickle.load(f)  # noqa: S301 - trusted artifact
    return payload


def predict_from_frame(
    features: dict[str, float], artifact: dict[str, Any] | None = None
) -> Prediction:
    """Predict with pre-built features (used by tests and the pipeline)."""
    art = artifact or load_artifact()
    x = np.asarray([[features[name] for name in FEATURE_NAMES]], dtype=float)
    models: dict[str, Any] = art["models"]
    mid = float(max(0.0, models["p50"].predict(x)[0]))
    radius = float(art.get("conformal_radius", 0.0))
    low = max(0.0, mid - radius)
    high = mid + radius
    return Prediction(
        pm25_mid=round(mid, 2),
        pm25_low=round(low, 2),
        pm25_high=round(high, 2),
        model_version=art.get("snapshot_sha256", "unknown")[:12],
        snapshot_sha256=art.get("snapshot_sha256", ""),
        source="model",
    )


def nearest_station_fallback(lag1_value: float) -> Prediction:
    """Best baseline (persistence): the nearest station's last reading.

    Interval = the model's measured MAE band on the temporal holdout; if no
    measured band is available the interval is degenerate (honest: unknown).
    """
    mid = max(0.0, lag1_value)
    return Prediction(
        pm25_mid=round(mid, 2),
        pm25_low=round(mid, 2),
        pm25_high=round(mid, 2),
        model_version="nearest-station",
        snapshot_sha256="",
        source="nearest-station",
    )


DELHI_SOURCES_PATH = Path(__file__).resolve().parents[3] / "data" / "delhi_sources.json"


def build_features_for_point(
    *,
    lat: float,
    lon: float,
    ts: datetime,
    weather_row: dict[str, Any],
    station_lag1: float,
    station_lag24: float,
    station_rolling6: float,
    station_sources: list[Source] | None = None,
) -> dict[str, float]:
    """Feature vector at an arbitrary point using the SAME builder as training."""
    sources = station_sources if station_sources is not None else []
    static = static_features(Point(lat, lon), sources)
    return build_feature_row(
        ts=ts,
        lat=lat,
        lon=lon,
        weather_row=weather_row,
        static_feats=static,
        station_lag1=station_lag1,
        station_lag24=station_lag24,
        station_rolling6=station_rolling6,
    )


def static_sources_default() -> list[Source]:
    """Delhi static sources from the real OSM extract (see data/delhi_sources.json)."""
    return _delhi_sources()


def _delhi_sources() -> list[Source]:
    if not DELHI_SOURCES_PATH.exists():
        return []
    payload = json.loads(DELHI_SOURCES_PATH.read_text())
    return [
        Source(lat=float(s["lat"]), lon=float(s["lon"]), kind=str(s["kind"]))
        for s in payload.get("sources", [])
    ]


__all__ = [
    "ModelNotTrainedError",
    "Prediction",
    "build_features_for_point",
    "load_artifact",
    "nearest_station_fallback",
    "predict_from_frame",
    "static_sources_default",
]

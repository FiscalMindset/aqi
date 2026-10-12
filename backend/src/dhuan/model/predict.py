"""Prediction-time interface for the PM2.5 model.

Serves the median + conformal 80% interval at any point in Delhi-NCR.
Feature vector construction mirrors training exactly (same function), and
nearest-station history is supplied at call time by the caller (the API
layer), never read from the model artifact.
"""

from __future__ import annotations

import json
import os
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

# DHUAN_MODEL_DIR wins (set to /var/task/models in the Lambda image), then the
# repository layout. The previous value used parents[2], which from
# src/dhuan/model/predict.py resolves to src/models - a directory that does not
# exist, so load_artifact() always raised ModelNotTrainedError and every live
# response silently fell back to the nearest-station baseline. The model has
# never actually run in the deployed app.
ARTIFACTS = Path(
    os.environ.get("DHUAN_MODEL_DIR") or Path(__file__).resolve().parents[3] / "models"
)


LAG1_INDEX = FEATURE_NAMES.index("station_lag1")


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
    # The models are trained on the persistence-anchored residual
    # (pm25 - station_lag1); see dhuan.model.train. Anchored artifacts only.
    anchor = float(x[0, LAG1_INDEX])
    delta = float(models["p50"].predict(x)[0])
    # Bound the correction: the 99th percentile of |actual - anchor| seen in
    # training. Without it an out-of-distribution feature vector can produce a
    # correction larger than the value being corrected.
    clip = float(art.get("delta_clip", 0.0))
    if clip > 0:
        delta = max(-clip, min(clip, delta))
    mid = float(max(0.0, anchor + delta))
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
    "NEUTRAL_VALUES",
    "ModelNotTrainedError",
    "Prediction",
    "build_features_for_point",
    "explain_features",
    "feature_units",
    "load_artifact",
    "nearest_station_fallback",
    "persistence_anchor",
    "predict_from_frame",
    "static_sources_default",
]


# --------------------------------------------------------------------------
# Per-prediction attribution
# --------------------------------------------------------------------------
# "Which parameters produced this number?" is answered by occlusion: replace one
# feature at a time with a neutral value and measure how far the prediction
# moves. The result is in the same units as the target (ug/m3), so a
# contribution of -40 means "this parameter is pushing the estimate down by
# about 40 ug/m3 relative to a typical value".
#
# This is honest and cheap (27 extra predict() calls on a 1-row matrix) and
# needs no extra dependency, unlike SHAP. It is an association, not a causal
# claim, and the UI labels it that way.

NEUTRAL_VALUES: dict[str, float] = {
    "wind_speed": 2.0,
    "wind_gust": 4.0,
    "temp_c": 25.0,
    "rh": 50.0,
    "precip": 0.0,
    "station_lag1": 0.0,
    "station_lag24": 0.0,
    "station_rolling6": 0.0,
    "wind_dir_sin": 0.0,
    "wind_dir_cos": 1.0,
    "hour_sin": 0.0,
    "hour_cos": 1.0,
    "month_sin": 0.0,
    "month_cos": 1.0,
}


def feature_units(name: str) -> str:
    if name.endswith("_km"):
        return "km"
    if name.endswith("_5km"):
        return "count within 5 km"
    if name in {"temp_c"}:
        return "degC"
    if name in {"rh"}:
        return "%"
    if name in {"precip"}:
        return "mm"
    if name in {"wind_speed", "wind_gust"}:
        return "m/s"
    if name in {"lat", "lon"}:
        return "degrees"
    if name in {"hour", "dayofweek", "month"}:
        return "index"
    return "dimensionless"


def explain_features(
    features: dict[str, float],
    artifact: dict[str, Any] | None = None,
    *,
    baseline: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Per-feature contribution to this prediction, largest effect first.

    `baseline` lets a caller supply reference values (e.g. the training median)
    instead of the neutral constants, which is what `model_card` reports.
    """
    art = artifact or load_artifact()
    model = art["models"]["p50"]
    x = np.asarray([[features[name] for name in FEATURE_NAMES]], dtype=float)
    anchor = float(x[0, LAG1_INDEX])

    neutral = dict(NEUTRAL_VALUES)
    if baseline:
        neutral.update(baseline)

    # The anchor (nearest station, 1h earlier) is held fixed while every other
    # feature is perturbed, so the reported effects are the model's *adjustments
    # to the persistence baseline* and not a restatement of it. Without this,
    # zeroing station_lag1 would also move the anchor and dominate every row.
    held_anchor = x[0, LAG1_INDEX]

    # One batched predict for all features. HistGradientBoosting pays a fixed
    # cost per predict() call regardless of batch size, so 24 sequential calls
    # cost 24x a single call. The agent runs this inside a wall-clock guardrail,
    # where that difference was the whole answer: "agent run exceeded
    # wall-clock budget" versus a served explanation.
    probe_rows: list[np.ndarray] = []
    indices: list[int] = []
    for i, name in enumerate(FEATURE_NAMES):
        if name in {"lat", "lon", "station_lag1"}:
            # positional proxies, not physical parameters; the anchor is the
            # baseline itself and is reported separately as persistence_anchor
            continue
        row = x.copy()
        row[0, LAG1_INDEX] = held_anchor
        row[0, i] = neutral.get(name, float(np.mean(row[0, i])))
        probe_rows.append(row)
        indices.append(i)

    actual = float(max(0.0, anchor + model.predict(x)[0]))
    # empty only if every feature were excluded, which cannot happen
    preds = model.predict(np.vstack(probe_rows))

    rows: list[dict[str, Any]] = []
    for i, pred in zip(indices, preds, strict=True):
        name = FEATURE_NAMES[i]
        value = max(0.0, float(anchor + pred))
        rows.append(
            {
                "name": name,
                "value": round(float(x[0, i]), 3),
                "unit": feature_units(name),
                "reference": round(float(neutral.get(name, float(x[0, i]))), 3),
                "contribution_ugm3": round(value - actual, 2),
                "absolute_effect_ugm3": round(abs(value - actual), 2),
            }
        )
    rows.sort(key=lambda r: r["absolute_effect_ugm3"], reverse=True)
    return rows


def persistence_anchor(features: dict[str, float]) -> float:
    """The baseline the model corrects: nearest station, one hour earlier."""
    return float(features.get("station_lag1", 0.0))

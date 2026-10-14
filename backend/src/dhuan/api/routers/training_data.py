"""GET /v1/training-data - what the model was actually built from.

Counters are computed from the shipped snapshot on first request and cached,
because the alternative is a hand-written number that drifts from the data the
next time training runs. A page claiming "we trained on N observations" is only
worth anything if N is derived, not typed.

Everything here is a count or a date read from files in the image. Nothing is
modelled, estimated or rounded for presentation.
"""

from __future__ import annotations

import gzip
import json
from functools import lru_cache
from typing import Any

from fastapi import APIRouter

from dhuan.api.routers.model_card import _load as _load_metrics
from dhuan.core.logging import get_logger
from dhuan.model.features import DATA_DIR, FEATURE_NAMES

router = APIRouter(prefix="/v1", tags=["training-data"])
logger = get_logger("api.training_data")

SNAPSHOT_GZ = "training_snapshot.json.gz"
SNAPSHOT_RAW = "training_snapshot.json"


@lru_cache(maxsize=1)
def _summary() -> dict[str, Any]:
    gz = DATA_DIR / SNAPSHOT_GZ
    raw = DATA_DIR / SNAPSHOT_RAW
    payload: dict[str, Any]
    if gz.exists():
        with gzip.open(gz, "rt") as handle:
            payload = json.loads(handle.read())
    elif raw.exists():
        payload = json.loads(raw.read_text())
    else:
        raise FileNotFoundError("no training snapshot in the image")

    stations = payload.get("stations") or []
    weather = payload.get("weather") or []
    if not stations:
        raise ValueError("training snapshot contains no station rows")

    by_station: dict[Any, int] = {}
    first: str | None = None
    last: str | None = None
    values: list[float] = []
    for row in stations:
        sid = row.get("location_id")
        by_station[sid] = by_station.get(sid, 0) + 1
        stamp = str(row.get("datetime") or "")
        if stamp:
            first = stamp if first is None or stamp < first else first
            last = stamp if last is None or stamp > last else last
        try:
            values.append(float(row["value"]))
        except (KeyError, TypeError, ValueError):
            continue

    per_station = sorted(by_station.values(), reverse=True)
    return {
        "station_observations": len(stations),
        "weather_observations": len(weather),
        "stations": len(by_station),
        "busiest_station_rows": per_station[0] if per_station else 0,
        "median_station_rows": per_station[len(per_station) // 2] if per_station else 0,
        "first_observation": (first or "")[:10],
        "last_observation": (last or "")[:10],
        "observed_min_ugm3": min(values) if values else 0.0,
        "observed_max_ugm3": max(values) if values else 0.0,
        "observed_mean_ugm3": round(sum(values) / len(values), 1) if values else 0.0,
        "sources": (payload.get("provenance") or {}).get("sources", {}),
    }


@router.get(
    "/training-data",
    summary="What the model was trained on: counts, dates and features",
    response_description=(
        "Observation counts, coverage window, observed PM2.5 range, the feature "
        "list, and the shipped evaluation metrics. All derived from files."
    ),
)
async def training_data() -> dict[str, Any]:
    try:
        summary = dict(_summary())
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("training_summary_unavailable: %s", exc)
        return {
            "available": False,
            "reason": "The training snapshot is not present in this image.",
            "features": list(FEATURE_NAMES),
            "metrics": _load_metrics(),
        }
    metrics = _load_metrics()
    return {
        "available": True,
        **summary,
        "features": list(FEATURE_NAMES),
        "feature_count": len(FEATURE_NAMES),
        "metrics": {
            "version": metrics.get("version"),
            "created_utc": metrics.get("created_utc"),
            "n_rows": metrics.get("n_rows"),
            "winner": metrics.get("winner"),
            "temporal_holdout": metrics.get("temporal_holdout", {}),
            "loso_mean": metrics.get("loso_mean", {}),
            "baselines": metrics.get("baselines", {}),
        },
    }


__all__ = ["router", "training_data"]

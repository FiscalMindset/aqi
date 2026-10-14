"""GET /v1/model — the algorithm, its held-out accuracy, and its provenance.

Every number here is read from backend/models/metrics.json, which is written by
`python -m dhuan.model.train` and never by hand. The endpoint exists so the UI
can show the real model card instead of a marketing claim.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from dhuan.api.models import (
    ModelCardOut,
    ModelMetrics,
    ModelVersionOut,
    ModelVersionsOut,
)

router = APIRouter(prefix="/v1", tags=["model"])

ALGORITHM = (
    "HistGradientBoostingRegressor (scikit-learn), quantile loss at p10/p50/p90, "
    "trained on the persistence-anchored residual (pm25 - station_lag1) so that "
    "the nearest-station reading is the null hypothesis the model must beat"
)


def _metrics_file() -> Path | None:
    from dhuan.model.predict import ARTIFACTS

    candidate = ARTIFACTS / "metrics.json"
    return candidate if candidate.exists() else None


@lru_cache
def _load() -> dict[str, Any]:
    path = _metrics_file()
    if path is None:
        return {}
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def _to_metrics(raw: dict[str, Any]) -> ModelMetrics:
    def num(key: str) -> float | None:
        value = raw.get(key)
        if value is None:
            return None
        # NaN (e.g. coverage for a point baseline) is not representable in JSON
        return None if value != value else float(value)  # noqa: PLR0124

    return ModelMetrics(
        n_train=int(raw.get("n_train", 0)),
        n_test=int(raw.get("n_test", 0)),
        mae=float(raw.get("mae", 0.0)),
        rmse=float(raw.get("rmse", 0.0)),
        r2=float(raw.get("r2", 0.0)),
        bias=float(raw.get("bias", 0.0)),
        coverage80=num("coverage80"),
        mean_width=num("mean_width"),
    )


@router.get(
    "/model",
    summary="Model card: algorithm, held-out accuracy, training provenance",
    response_description="Everything needed to judge the estimate.",
)
async def model_card() -> ModelCardOut:
    data = _load()
    if not data:
        raise RuntimeError("model metrics not generated; run make train")
    baselines = {
        name: _to_metrics({**raw, "n_train": data["temporal_holdout"]["n_train"],
                           "n_test": data["temporal_holdout"]["n_test"]})
        for name, raw in (data.get("baselines") or {}).items()
    }
    features = list(data.get("features") or [])
    radius = float(data.get("conformal_radius_ugm3") or 0.0)
    if not radius:
        # stored in the note; recompute from the served artifact when possible
        try:
            from dhuan.model.predict import load_artifact

            radius = float(load_artifact().get("conformal_radius", 0.0))
        except Exception:
            radius = 0.0
    return ModelCardOut(
        algorithm=ALGORITHM,
        trained_at_utc=str(data.get("created_utc", "")),
        snapshot_sha256=str(data.get("snapshot_sha256", "")),
        n_rows=int(data.get("n_rows", 0)),
        stations=list(data.get("stations") or []),
        temporal_holdout=_to_metrics(data["temporal_holdout"]),
        leave_one_station_out=_to_metrics(data["loso_mean"]),
        baselines=baselines,
        winner=str(data.get("winner", "")),
        features=features,
        n_features=len(features),
        conformal_radius_ugm3=radius,
        notes=list(data.get("notes") or []),
    )


@router.get(
    "/v1/model/versions",
    response_model=ModelVersionsOut,
    summary="Every retained model version and what it scored",
    response_description="Version registry, oldest first, with the current one marked.",
)
def model_versions() -> ModelVersionsOut:
    """Retained model versions, newest last.

    Reading from a registry rather than a single metrics file means a retrain
    that made the model worse is visible instead of overwritten. `artifact_present`
    is false once the pickle has been pruned; the registry row and the commit
    that produced it remain, so the model can still be recovered from git.
    """
    from dhuan.model.versions import summary

    reg = summary()
    current = None
    try:
        from dhuan.model.versions import load_registry

        current = load_registry().get("current")
    except Exception:
        current = None
    return ModelVersionsOut(current=current, versions=[ModelVersionOut(**v) for v in reg])

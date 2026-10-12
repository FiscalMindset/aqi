"""Read the model's measured accuracy for use in a grounded explanation.

The numbers come from `backend/models/metrics.json`, which is written only by
`model/evaluate.py`. Nothing here computes or estimates accuracy; it is a thin
reader so the explanation and the model card can never disagree.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from dhuan.model.predict import ARTIFACTS


@lru_cache(maxsize=1)
def _metrics() -> dict[str, Any]:
    path = ARTIFACTS / "metrics.json"
    if not path.exists():
        return {}
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def _section(name: str) -> dict[str, Any]:
    value = _metrics().get(name)
    return value if isinstance(value, dict) else {}


def model_accuracy_summary() -> dict[str, float] | None:
    """Held-out MAE and the unseen-station MAE, or None if untrained.

    `unseen_mae` is the number that matters most to a user standing on a street
    with no monitor: it is the error at locations the model never saw in
    training, which is exactly the problem this product claims to solve.
    """
    temporal = _section("temporal_holdout")
    mae = temporal.get("mae")
    if mae is None or mae != mae:  # noqa: PLR0124 - NaN check
        return None
    summary: dict[str, float] = {"mae": float(mae)}
    # leave-one-station-out: the error at monitors the model never trained on,
    # which is the honest number for someone standing on an unmonitored street
    loso = _section("loso_mean")
    if loso.get("mae") is not None and loso["mae"] == loso["mae"]:
        summary["unseen_mae"] = float(loso["mae"])
    baselines = _section("baselines")
    persistence = baselines.get("persistence")
    if isinstance(persistence, dict) and persistence.get("mae") is not None:
        summary["persistence_mae"] = float(persistence["mae"])
    return summary


__all__ = ["model_accuracy_summary"]

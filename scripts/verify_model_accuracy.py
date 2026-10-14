"""Independent accuracy check on the SHIPPED model.

This does NOT retrain. It loads backend/models/model.pkl exactly as the API
does, replays the temporal holdout the training run used, and reports the
measured error. The point is to let the shipped numbers be checked rather than
trusted: if this disagrees with metrics.json, metrics.json is wrong and the
product is advertising an accuracy it cannot back up.

It measures the same thing the API serves - the median model plus the conformal
radius - not the raw quantile spread, because the raw p10/p90 under-cover and
the conformal interval is what a reader actually sees.

Run:  backend/.venv/bin/python scripts/verify_model_accuracy.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from dhuan.model.features import (  # noqa: E402
    FEATURE_NAMES,
    build_training_frame,
    load_snapshot,
)
from dhuan.model.predict import load_artifact  # noqa: E402
from dhuan.model.train import TEMPORAL_HOLDOUT_FRACTION, persistence_anchor  # noqa: E402


def _measure(art: dict, matrix: np.ndarray, te: np.ndarray, actual: np.ndarray) -> dict:
    """Score an artifact on the same rows the way the API serves."""
    from dhuan.model.train import persistence_anchor

    clip = float(art.get("delta_clip", 0.0))
    radius = float(art.get("conformal_radius", 0.0))
    anchor = persistence_anchor(matrix[te])
    delta = np.asarray(art["models"]["p50"].predict(matrix[te]), dtype=float)
    if clip > 0:
        delta = np.clip(delta, -clip, clip)
    mid = np.maximum(0.0, anchor + delta)
    lo = np.maximum(0.0, mid - radius)
    hi = mid + radius
    err = actual - mid
    var = float(np.var(actual))
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "bias": float(np.mean(err)),
        "r2": float(1 - np.mean(err**2) / var) if var > 0 else float("nan"),
        "coverage": float(np.mean((actual >= lo) & (actual <= hi))),
        "radius": radius,
    }


def compare_versions(matrix: np.ndarray, te: np.ndarray, actual: np.ndarray) -> int:
    """Score every retained version on the SAME current holdout.

    This is the point of keeping versions: a retrain is only meaningful if you
    can ask "is this actually better than the last one?" on identical data
    rather than comparing two numbers measured on different snapshots.
    """
    import sys as _sys

    _sys.path.insert(0, str(ROOT / "backend" / "src"))
    from dhuan.model.versions import load_artifact_version, load_registry

    reg = load_registry()
    versions = reg.get("versions", [])
    if not versions:
        print("No retained versions yet. Run `make train` once to record one.")
        return 0

    print(f"{'version':26} {'MAE':>7} {'RMSE':>7} {'R2':>7} {'cov':>7} {'rows':>10}  artifact")
    print("-" * 82)
    best = None
    for entry in versions:
        vid = entry["version_id"]
        try:
            art = load_artifact_version(vid)
        except (FileNotFoundError, KeyError) as exc:
            print(f"{vid:26} {'-':>7} {'-':>7} {'-':>7} {'-':>7} {entry.get('n_rows', 0):>10,}  {str(exc)[:22]}")
            continue
        m = _measure(art, matrix, te, actual)
        mark = " <- current" if vid == reg.get("current") else ""
        print(
            f"{vid:26} {m['mae']:7.2f} {m['rmse']:7.2f} {m['r2']:7.3f} "
            f"{m['coverage'] * 100:6.1f}% {entry.get('n_rows', 0):>10,}  on disk{mark}"
        )
        if best is None or m["mae"] < best[1]:
            best = (vid, m["mae"])
    print()
    if best:
        print(f"Best MAE on this holdout: {best[0]} at {best[1]:.2f} ug/m3")
    return 0


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--compare", action="store_true", help="score every retained version")
    ap.add_argument("--version", help="score one retained version id")
    args = ap.parse_args()

    print("Loading snapshot (591k rows)...", flush=True)
    snapshot = load_snapshot()
    rows, labels, meta = build_training_frame(snapshot)
    matrix = np.asarray([[row[name] for name in FEATURE_NAMES] for row in rows], dtype=float)
    y = np.asarray(labels, dtype=float)
    ts = [datetime.fromisoformat(m["ts"]) for m in meta]

    ordered = sorted(ts)
    holdout_start = ordered[int(len(ordered) * (1 - TEMPORAL_HOLDOUT_FRACTION))]
    te = np.asarray([t >= holdout_start for t in ts])
    print(f"Holdout rows: {int(te.sum()):,} of {len(y):,}", flush=True)

    art = load_artifact()
    clip = float(art.get("delta_clip", 0.0))
    radius = float(art.get("conformal_radius", 0.0))
    anchor = persistence_anchor(matrix[te])

    # Replicate predict_from_frame exactly: median model on the anchored
    # residual, clipped, added back to the anchor.
    delta = np.asarray(art["models"]["p50"].predict(matrix[te]), dtype=float)
    if clip > 0:
        delta = np.clip(delta, -clip, clip)
    mid = np.maximum(0.0, anchor + delta)
    lo = np.maximum(0.0, mid - radius)
    hi = mid + radius

    actual = y[te]

    def report(name: str, p: np.ndarray, lo_: np.ndarray, hi_: np.ndarray) -> dict[str, float]:
        err = actual - p
        mae = float(np.mean(np.abs(err)))
        rmse = float(np.sqrt(np.mean(err**2)))
        bias = float(np.mean(err))
        var = float(np.var(actual))
        r2 = float(1 - np.mean(err**2) / var) if var > 0 else float("nan")
        cov = float(np.mean((actual >= lo_) & (actual <= hi_)))
        print(f"\n{name}")
        print(f"  MAE                   {mae:9.2f} ug/m3")
        print(f"  RMSE                  {rmse:9.2f} ug/m3")
        print(f"  Bias                  {bias:+9.2f} ug/m3")
        print(f"  R2                    {r2:9.3f}")
        print(f"  interval coverage     {cov * 100:8.1f}%   (nominal 80%)")
        return {"mae": mae, "rmse": rmse, "bias": bias, "r2": r2, "coverage": cov}

    print("=" * 64)
    model = report("SHIPPED MODEL on held-out future hours", mid, lo, hi)
    base = report("BASELINE: repeat the last station reading", anchor, anchor, anchor)

    print("=" * 64)
    gain = (1 - model["mae"] / base["mae"]) * 100
    print(f"Model vs persistence baseline: {gain:+.1f}% MAE")
    print(f"Served interval is +/- {radius:.1f} ug/m3 (conformal), model error MAE {model['mae']:.1f}")

    shipped = json.loads((ROOT / "backend" / "models" / "metrics.json").read_text())
    claimed = shipped["temporal_holdout"]
    print("\nWhat metrics.json advertises vs what was just measured:")
    rows_out = [
        ("MAE", claimed["mae"], model["mae"], 0.5),
        ("RMSE", claimed["rmse"], model["rmse"], 0.5),
        ("R2", claimed["r2"], model["r2"], 0.05),
    ]
    problems: list[str] = []
    for label, c, m, tol in rows_out:
        ok = abs(c - m) <= tol
        print(f"  {label:5} advertised {c:8.3f}   measured {m:8.3f}   {'ok' if ok else 'MISMATCH'}")
        if not ok:
            problems.append(f"{label}: advertised {c:.3f}, measured {m:.3f}")

    print()
    if problems:
        print("FAIL - the advertised accuracy does not match the shipped model:")
        for p in problems:
            print("  -", p)
        return 1
    print("PASS - the advertised accuracy matches a fresh measurement of the shipped model.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
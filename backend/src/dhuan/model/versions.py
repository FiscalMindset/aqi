"""Versioned model retention.

A single overwritten `model.pkl` cannot answer "did this get worse, or did it
just change?". Each retrain is therefore stored as its own artifact and recorded
in a small registry, so a past model can be re-evaluated against current data
and the difference explained.

The registry is JSON and small enough to track in git. The pickles are not:
a model is ~6 MB, and committing every retrain would bury the source history
under binaries. They are written to `models/versions/` and gitignored. Older
committed models remain retrievable from git history (`git show
<commit>:backend/models/model.pkl`), and the registry records the commit when
one is known, so a version is never truly lost.
"""

from __future__ import annotations

import json
import pickle
import shutil
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ARTIFACTS = Path(__file__).resolve().parents[3] / "models"
VERSIONS_DIR = ARTIFACTS / "versions"
REGISTRY = ARTIFACTS / "versions.json"

# Cap the on-disk pile. Models stop being useful for explanation long before
# they stop being large; the registry keeps the full history regardless.
KEEP_ARTIFACTS = 10


def _git_commit() -> str | None:
    try:
        # Full path: a bare "git" resolves from PATH and a poisoned PATH entry
        # would run an arbitrary binary during a training run.
        git = shutil.which("git") or "/usr/bin/git"
        # Read-only plumbing call to a fixed absolute binary with fixed arguments.
        out = subprocess.run(  # noqa: S603
            [git, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def version_id_for(snapshot_sha: str, when: datetime) -> str:
    stamp = when.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{snapshot_sha[:8]}"


def _record_version(
    payload: dict[str, Any],
    evaluation: Any,
    conformal_radius: float,
) -> str:
    """Persist the artifact and append it to the registry. Returns the id."""
    when = datetime.fromisoformat(evaluation.created_utc)
    vid = version_id_for(evaluation.snapshot_sha256, when)

    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    artifact = VERSIONS_DIR / f"{vid}.pkl"
    if not artifact.exists():
        with artifact.open("wb") as f:
            pickle.dump(payload, f)

    registry = load_registry()
    entries = [e for e in registry["versions"] if e["version_id"] != vid]
    entries.append(
        {
            "version_id": vid,
            "trained_utc": evaluation.created_utc,
            "snapshot_sha256": evaluation.snapshot_sha256,
            "n_rows": evaluation.n_rows,
            "n_stations": len(evaluation.stations),
            "n_features": len(payload.get("features", [])),
            "conformal_radius_ugm3": round(float(conformal_radius), 2),
            "delta_clip": round(float(payload.get("delta_clip", 0.0)), 2),
            "winner": evaluation.winner,
            "temporal_holdout": {
                k: round(float(v), 4) if isinstance(v, (int, float)) else v
                for k, v in evaluation.temporal_holdout.items()
            },
            "unseen_station": {
                k: round(float(v), 4) if isinstance(v, (int, float)) else v
                for k, v in evaluation.loso_mean.items()
            },
            "baselines": {
                k: round(float(v.get("mae", 0.0)), 4)
                for k, v in evaluation.baselines.items()
            },
            "artifact": f"models/versions/{vid}.pkl",
            "git_commit": _git_commit(),
        }
    )
    entries.sort(key=lambda e: e["trained_utc"])
    registry["versions"] = entries
    registry["current"] = vid
    REGISTRY.write_text(json.dumps(registry, indent=2) + "\n")

    _prune(entries)
    return vid


def _prune(entries: list[dict[str, Any]]) -> None:
    """Drop the oldest artifacts beyond KEEP_ARTIFACTS, keeping registry rows."""
    if len(entries) <= KEEP_ARTIFACTS:
        return
    for old in entries[: len(entries) - KEEP_ARTIFACTS]:
        path = ARTIFACTS.parent.parent / old["artifact"]
        try:
            path.unlink()
        except OSError:
            continue
        old["artifact_present"] = False
    REGISTRY.write_text(
        json.dumps(
            {"current": entries[-1]["version_id"], "versions": entries}, indent=2
        )
        + "\n"
    )


def load_registry() -> dict[str, Any]:
    if REGISTRY.exists():
        try:
            data = json.loads(REGISTRY.read_text())
            if isinstance(data, dict) and isinstance(data.get("versions"), list):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"current": None, "versions": []}


def load_artifact_version(version_id: str) -> dict[str, Any]:
    """Load a retained artifact by id. Raises if it has been pruned."""
    for entry in load_registry()["versions"]:
        if entry["version_id"] == version_id:
            path = ARTIFACTS.parent.parent / entry["artifact"]
            if not path.exists():
                raise FileNotFoundError(
                    f"artifact for {version_id} was pruned; retrieve it from git "
                    f"history at commit {entry.get('git_commit')}"
                )
            # Artifacts are written by this module and never come from a user
            # upload, so deserialising our own pickle is the intended use.
            with path.open("rb") as f:
                payload: dict[str, Any] = pickle.load(f)  # noqa: S301
            return payload
    raise KeyError(f"unknown model version: {version_id}")


def summary() -> list[dict[str, Any]]:
    """Registry rows with only what a comparison needs."""
    out = []
    for e in load_registry()["versions"]:
        out.append(
            {
                "version_id": e["version_id"],
                "trained_utc": e["trained_utc"],
                "n_rows": e["n_rows"],
                "n_stations": e.get("n_stations"),
                "snapshot_sha256": e["snapshot_sha256"][:12],
                "conformal_radius_ugm3": e.get("conformal_radius_ugm3"),
                "temporal_mae": e["temporal_holdout"].get("mae"),
                "temporal_rmse": e["temporal_holdout"].get("rmse"),
                "temporal_r2": e["temporal_holdout"].get("r2"),
                "unseen_mae": e["unseen_station"].get("mae"),
                "baseline_mae": e.get("baselines", {}).get("persistence-lag1h"),
                "git_commit": e.get("git_commit"),
                "artifact_present": (ARTIFACTS.parent.parent / e["artifact"]).exists(),
            }
        )
    return out


__all__ = [
    "REGISTRY",
    "VERSIONS_DIR",
    "asdict",
    "load_artifact_version",
    "load_registry",
    "summary",
    "version_id_for",
]

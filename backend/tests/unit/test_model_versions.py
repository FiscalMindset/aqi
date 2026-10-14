"""Retained model versions.

A single overwritten model.pkl cannot answer "did this get worse, or did it just
change?". These tests pin the behaviour that makes the difference: every retrain
is kept addressable and comparable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dhuan.model import versions as mv


def _entry(vid: str, when: str, mae: float) -> dict:
    return {
        "version_id": vid,
        "trained_utc": when,
        "snapshot_sha256": "c7836258415ae075b78a42495f23025871f36047348589588e039da60152ab7a",
        "n_rows": 591372,
        "n_stations": 73,
        "n_features": 27,
        "conformal_radius_ugm3": 15.0,
        "delta_clip": 46.0,
        "winner": "quantile-model",
        "temporal_holdout": {"mae": mae, "rmse": 26.3, "r2": 0.535},
        "unseen_station": {"mae": 10.6, "rmse": 21.7, "r2": 0.566},
        "baselines": {"persistence-lag1h": 11.64},
        "artifact": f"models/versions/{vid}.pkl",
        "git_commit": "abc1234",
    }


@pytest.fixture
def fake_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    artifacts = tmp_path / "models"
    (artifacts / "versions").mkdir(parents=True)
    reg = artifacts / "versions.json"
    monkeypatch.setattr(mv, "ARTIFACTS", artifacts)
    monkeypatch.setattr(mv, "VERSIONS_DIR", artifacts / "versions")
    monkeypatch.setattr(mv, "REGISTRY", reg)
    return artifacts


def test_version_id_is_stable_for_the_same_snapshot_and_instant() -> None:
    from datetime import UTC, datetime

    when = datetime(2026, 10, 14, 12, 0, 0, tzinfo=UTC)
    a = mv.version_id_for("c7836258415ae075b78a42495f2302587", when)
    b = mv.version_id_for("c7836258415ae075b78a42495f2302587", when)
    assert a == b
    assert a.startswith("20261014T120000Z-")
    assert a.endswith("c7836258")


def test_version_id_differs_when_the_snapshot_changes() -> None:
    from datetime import UTC, datetime

    when = datetime(2026, 10, 14, tzinfo=UTC)
    assert mv.version_id_for("aaaa1111", when) != mv.version_id_for("bbbb2222", when)


def test_registry_survives_a_missing_or_corrupt_file(tmp_path: Path) -> None:
    reg = tmp_path / "versions.json"
    assert mv.load_registry() == {"current": None, "versions": []}
    reg.write_text("{ not json")
    assert mv.load_registry() == {"current": None, "versions": []}


def test_summary_keeps_only_comparable_fields(fake_registry: Path) -> None:
    fake_registry.joinpath("versions.json").write_text(
        json.dumps(
            {
                "current": "v2",
                "versions": [
                    _entry("v1", "2026-10-01T00:00:00+00:00", 12.0),
                    _entry("v2", "2026-10-14T00:00:00+00:00", 9.9),
                ],
            }
        )
    )
    rows = mv.summary()
    assert [r["version_id"] for r in rows] == ["v1", "v2"]
    assert rows[1]["temporal_mae"] == 9.9
    assert rows[1]["baseline_mae"] == 11.64
    # artifact_present must be honest: no pickles were written in this test
    assert rows[0]["artifact_present"] is False


def test_loading_an_unknown_version_is_a_clear_error(fake_registry: Path) -> None:
    with pytest.raises(KeyError):
        mv.load_artifact_version("does-not-exist")


def test_a_pruned_artifact_explains_where_to_recover_it(fake_registry: Path) -> None:
    # Registry row survives, pickle pruned: the error must point at git, not
    # fail with a bare FileNotFoundError.
    fake_registry.joinpath("versions.json").write_text(
        json.dumps({"current": "v1", "versions": [_entry("v1", "2026-10-01T00:00:00+00:00", 12.0)]})
    )
    with pytest.raises(FileNotFoundError) as caught:
        mv.load_artifact_version("v1")
    assert "abc1234" in str(caught.value)

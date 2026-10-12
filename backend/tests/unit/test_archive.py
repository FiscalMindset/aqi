"""Tests for the keyless OpenAQ public-archive station store.

These guard the claim that lets us delete demo mode: with no API credential the
product still answers from real observations, and it is honest about how old
they are.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from dhuan.ingest.archive import (
    ArchiveUnavailableError,
    archive_age_seconds,
    archive_provenance,
    is_stale,
    load_index,
    maybe_decompress,
    newest_observation,
    parse_archive_csv,
    readings_near,
)


def _write_index(tmp_path: Path, *, newest: datetime, hours: int = 6) -> Path:
    stations = []
    for i, (lat, lon) in enumerate([(28.63, 77.22), (28.70, 77.10), (30.0, 75.0)]):
        series = [
            {"t": (newest - timedelta(hours=h)).isoformat(), "v": 100.0 + h + i}
            for h in range(hours, 0, -1)
        ]
        series.append({"t": newest.isoformat(), "v": 120.0 + i})
        stations.append(
            {
                "location_id": str(1000 + i),
                "name": f"Station {i}",
                "lat": lat,
                "lon": lon,
                "sensor_id": 500 + i,
                "latest": series[-1],
                "history": series,
            }
        )
    payload = {
        "schema": 1,
        "provenance": {"source": "openaq-public-archive", "stations": len(stations)},
        "stations": stations,
    }
    path = tmp_path / "station_index.json"
    path.write_text(json.dumps(payload))
    return path


@pytest.fixture
def index_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point the store at a small, controlled index."""
    from dhuan.ingest import archive

    newest = datetime(2026, 10, 8, 18, 0, tzinfo=UTC)
    path = _write_index(tmp_path, newest=newest)
    monkeypatch.setenv(archive.INDEX_ENV, str(path))
    archive.load_index.cache_clear()
    archive._all_readings.cache_clear()
    yield newest
    archive.load_index.cache_clear()
    archive._all_readings.cache_clear()


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------


def test_readings_near_returns_the_nearest_first(index_env: datetime) -> None:
    readings = readings_near(28.63, 77.22)
    assert len(readings) == 2  # the third station is 1000 km away
    assert readings[0].name == "Station 0"
    assert readings[0].value == 120.0


def test_readings_near_respects_the_radius(index_env: datetime) -> None:
    assert len(readings_near(28.63, 77.22, radius_km=1.0)) == 1


def test_only_the_latest_reading_per_station_is_returned(index_env: datetime) -> None:
    readings = readings_near(28.63, 77.22)
    assert len({r.station_id for r in readings}) == len(readings)
    assert max(r.observed_at for r in readings) == index_env


def test_future_readings_are_never_served(index_env: datetime) -> None:
    as_of = index_env - timedelta(days=1)
    assert readings_near(28.63, 77.22, as_of=as_of) == []


def test_readings_are_tagged_with_the_real_provider(index_env: datetime) -> None:
    assert all(r.provider == "openaq-public-archive" for r in readings_near(28.63, 77.22))


# --------------------------------------------------------------------------
# honesty about age
# --------------------------------------------------------------------------


def test_age_is_measured_from_the_data_not_assumed(index_env: datetime) -> None:
    as_of = index_env + timedelta(hours=10)
    assert archive_age_seconds(as_of) == pytest.approx(10 * 3600, rel=1e-3)


def test_recent_data_is_not_stale(index_env: datetime) -> None:
    assert not is_stale(index_env + timedelta(hours=2))


def test_old_data_is_flagged_stale(index_env: datetime) -> None:
    assert is_stale(index_env + timedelta(days=5))


def test_newest_observation_is_the_max_across_stations(index_env: datetime) -> None:
    assert newest_observation() == index_env


def test_provenance_is_exposed_for_the_model_card(index_env: datetime) -> None:
    assert archive_provenance()["source"] == "openaq-public-archive"


# --------------------------------------------------------------------------
# unavailability is a typed error, never a fabricated reading
# --------------------------------------------------------------------------


def test_missing_index_raises_a_typed_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dhuan.ingest import archive

    monkeypatch.setenv(archive.INDEX_ENV, str(tmp_path / "nope.json"))
    archive.load_index.cache_clear()
    with pytest.raises(ArchiveUnavailableError):
        archive_readings_near_or_fail()
    archive.load_index.cache_clear()


def archive_readings_near_or_fail():
    from dhuan.ingest.archive import readings_near as r

    return r(28.63, 77.22)


def test_corrupt_index_raises_a_typed_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dhuan.ingest import archive

    bad = tmp_path / "station_index.json"
    bad.write_text("{not json")
    monkeypatch.setenv(archive.INDEX_ENV, str(bad))
    archive.load_index.cache_clear()
    with pytest.raises(ArchiveUnavailableError):
        load_index()
    archive.load_index.cache_clear()


def test_index_without_stations_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dhuan.ingest import archive

    bad = tmp_path / "station_index.json"
    bad.write_text(json.dumps({"schema": 1, "provenance": {}}))
    monkeypatch.setenv(archive.INDEX_ENV, str(bad))
    archive.load_index.cache_clear()
    with pytest.raises(ArchiveUnavailableError):
        load_index()
    archive.load_index.cache_clear()


# --------------------------------------------------------------------------
# archive file parsing (used by the scheduled refresh)
# --------------------------------------------------------------------------


def test_parse_archive_csv_keeps_only_pm25() -> None:
    csv_text = "\n".join(
        [
            "locationid,sensorid,location,latitude,longitude,datetime,parameter,value",
            "17,122,A,28.5,77.1,2026-10-01T00:00:00+05:30,pm25,88.0",
            "17,122,A,28.5,77.1,2026-10-01T01:00:00+05:30,pm10,41.0",
        ]
    )
    rows = parse_archive_csv(csv_text)
    assert len(rows) == 1
    assert rows[0]["value"] == 88.0


def test_parse_archive_csv_skips_unusable_rows() -> None:
    csv_text = "\n".join(
        [
            "locationid,sensorid,location,latitude,longitude,datetime,parameter,value",
            "17,122,A,not-a-number,77.1,2026-10-01T00:00:00+05:30,pm25,88.0",
            "17,122,A,28.5,77.1,not-a-date,pm25,88.0",
            "17,122,A,28.5,77.1,2026-10-01T00:00:00+05:30,pm25,ok",
        ]
    )
    assert parse_archive_csv(csv_text) == []


def test_maybe_decompress_handles_both_encodings() -> None:
    import gzip

    plain = "a,b\n1,2"
    assert maybe_decompress(plain.encode()) == plain
    assert maybe_decompress(gzip.compress(plain.encode())) == plain


# --------------------------------------------------------------------------
# the committed index must be real and usable
# --------------------------------------------------------------------------


def test_the_committed_index_exists_and_is_real() -> None:
    """Guards against shipping a fabricated or empty index."""
    from dhuan.ingest.archive import DEFAULT_INDEX

    assert DEFAULT_INDEX.exists(), (
        f"the shipped station index is missing at {DEFAULT_INDEX}; "
        "run scripts/build_station_index.py"
    )
    data = json.loads(DEFAULT_INDEX.read_text())
    provenance = data["provenance"]
    assert "openaq" in str(provenance.get("source", "")).lower()
    assert len(data["stations"]) >= 20
    values = [
        point["v"]
        for station in data["stations"]
        for point in station["history"]
        if isinstance(point, dict) and "v" in point
    ]
    assert values
    assert all(0.0 <= float(v) <= 1000.0 for v in values)
    assert provenance.get("newest_observation")

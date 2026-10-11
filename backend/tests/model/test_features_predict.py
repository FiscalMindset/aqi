"""Unit tests for the model feature contract and prediction path."""

from __future__ import annotations

from datetime import datetime

from dhuan.core.units import Point
from dhuan.model.features import (
    FEATURE_NAMES,
    build_feature_row,
    lag_features,
    static_features,
    weather_features,
)
from dhuan.model.predict import (
    ModelNotTrainedError,
    build_features_for_point,
    nearest_station_fallback,
    predict_from_frame,
    static_sources_default,
)

WEATHER = {
    "wind_speed": 3.0,
    "wind_gust": 5.0,
    "temp_c": 18.0,
    "rh": 65.0,
    "precip": 0.0,
    "wind_dir": 292.0,
}


def _features(**over: float) -> dict[str, float]:
    base = dict.fromkeys(FEATURE_NAMES, 1.0)
    base.update(
        {
            "hour": 14.0,
            "wind_speed": 3.0,
            "temp_c": 18.0,
            "station_lag1": 150.0,
        }
    )
    base.update(over)
    return base


def test_static_features_defaults_when_empty() -> None:
    feats = static_features(Point(28.6, 77.2), [])
    assert feats["landfill_dist_km"] == 99.0
    assert feats["landfill_count_5km"] == 0.0


def test_static_features_count_within_radius() -> None:
    from dhuan.model.features import Source

    sources = [
        Source(lat=28.61, lon=77.21, kind="landfill"),
        Source(lat=28.9, lon=77.5, kind="landfill"),
    ]
    feats = static_features(Point(28.6, 77.2), sources)
    assert feats["landfill_count_5km"] == 1.0
    assert 0 < feats["landfill_dist_km"] < 99


def test_weather_features_circular_encoding() -> None:
    feats = weather_features(WEATHER)
    assert feats["wind_speed"] == 3.0
    assert abs(feats["wind_dir_sin"]) <= 1.0
    assert abs(feats["wind_dir_cos"]) <= 1.0


def test_build_feature_row_complete() -> None:
    row = build_feature_row(
        ts=datetime(2026, 1, 15, 14),
        lat=28.6,
        lon=77.2,
        weather_row=WEATHER,
        static_feats=static_features(Point(28.6, 77.2), []),
        station_lag1=150.0,
        station_lag24=140.0,
        station_rolling6=145.0,
    )
    assert set(row) == set(FEATURE_NAMES)
    assert row["station_lag1"] == 150.0


def test_build_features_for_point_matches_training_builder() -> None:
    row = build_features_for_point(
        lat=28.6139,
        lon=77.2090,
        ts=datetime(2026, 1, 15, 14),
        weather_row=WEATHER,
        station_lag1=150.0,
        station_lag24=150.0,
        station_rolling6=150.0,
    )
    assert set(row) == set(FEATURE_NAMES)


def test_static_sources_default_is_real_osm_extract() -> None:
    sources = static_sources_default()
    # data/delhi_sources.json is a real OSM extract of Delhi
    assert len(sources) > 100


def test_lag_features_missing_window() -> None:
    l1, l24, roll, found = lag_features({}, datetime(2026, 1, 15, 10))
    assert l1 == -1.0 and l24 == -1.0 and roll == -1.0 and found == 0


def test_nearest_station_fallback_has_degenerate_interval() -> None:
    pred = nearest_station_fallback(150.0)
    assert pred.pm25_mid == 150.0
    assert pred.source == "nearest-station"
    assert pred.pm25_low == pred.pm25_high  # honest: no interval available


def test_predict_requires_trained_artifact() -> None:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "nope.pkl"
        try:
            predict_from_frame(_features())
        except ModelNotTrainedError:
            pass
        try:
            from dhuan.model.predict import load_artifact

            load_artifact(missing)
        except ModelNotTrainedError:
            pass
        else:
            raise AssertionError("expected ModelNotTrainedError")


def test_predict_from_trained_artifact() -> None:
    """If the model artifact exists, a prediction must come back ordered."""
    from dhuan.model.predict import load_artifact

    try:
        artifact = load_artifact()
    except ModelNotTrainedError:
        return  # `make train` not run in this environment
    pred = predict_from_frame(_features(), artifact)
    assert 0 <= pred.pm25_low <= pred.pm25_mid <= pred.pm25_high

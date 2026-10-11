"""Pipeline task handlers: the full hourly flow against LocalStack."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.integration


def test_validate_and_merge_counts_and_rejects() -> None:
    from dhuan.pipeline.tasks import validate_and_merge

    out = validate_and_merge(
        {
            "ingested": [
                {"feed": "openaq", "records": 3, "ok": True},
                {"feed": "open-meteo", "records": 24, "ok": True},
                {"feed": "firms", "records": 0, "ok": False},
            ]
        }
    )
    assert out["total_records"] == 27
    assert out["ok"] is False
    assert out["rejects"][0]["feed"] == "firms"


def test_validate_and_merge_accepts_clean_branches() -> None:
    from dhuan.pipeline.tasks import validate_and_merge

    out = validate_and_merge(
        {"ingested": [{"feed": "openaq", "records": 3, "ok": True}]}
    )
    assert out["ok"] is True


def test_ingest_weather_writes_feed_record(dynamodb: object, env: dict[str, str]) -> None:
    from dhuan.pipeline.tasks import ingest_weather
    from dhuan.store.dynamodb import FeedsStore

    out = ingest_weather({})
    assert out["feed"] == "open-meteo"
    assert out["ok"] is True
    feeds = {f.feed: f for f in FeedsStore().all()}
    assert "open-meteo" in feeds
    assert feeds["open-meteo"].ok is True


def test_ingest_fires_soft_skips_without_key(dynamodb: object, env: dict[str, str]) -> None:
    from dhuan.pipeline.tasks import ingest_fires
    from dhuan.store.dynamodb import FeedsStore

    out = ingest_fires({})
    assert out["feed"] == "firms"
    assert out["ok"] is False  # soft skip, pipeline continues
    feeds = {f.feed: f for f in FeedsStore().all()}
    assert feeds["firms"].ok is False


def test_ingest_stations_without_key_records_failure(dynamodb: object, env: dict[str, str]) -> None:
    from dhuan.pipeline.tasks import ingest_stations
    from dhuan.store.dynamodb import FeedsStore

    with pytest.raises(Exception):  # noqa: B017 - the state machine catches it
        ingest_stations({})
    feeds = {f.feed: f for f in FeedsStore().all()}
    assert feeds["openaq"].ok is False


def test_persist_estimates_roundtrip(dynamodb: object, env: dict[str, str]) -> None:
    from dhuan.pipeline.tasks import persist_estimates
    from dhuan.store.dynamodb import EstimatesStore

    now = datetime.now(UTC)
    out = persist_estimates(
        {
            "predictions": [
                {
                    "cell": "88008990c7fffff",
                    "ts": now.isoformat(),
                    "pm25_low": 100.0,
                    "pm25_mid": 130.0,
                    "pm25_high": 160.0,
                },
                {
                    "cell": "88008990c3fffff",
                    "ts": now.isoformat(),
                    "pm25_low": 110.0,
                    "pm25_mid": 140.0,
                    "pm25_high": 170.0,
                },
            ]
        }
    )
    assert out["written"] == 2
    latest = EstimatesStore().get_latest("88008990c7fffff")
    assert float(latest["pm25_mid"]) == 130.0


def test_predict_grid_skips_without_model(dynamodb: object, env: dict[str, str]) -> None:
    from dhuan.model.predict import ARTIFACTS

    model = ARTIFACTS / "model.pkl"
    saved = model.read_bytes() if model.exists() else None
    try:
        if model.exists():
            model.unlink()
        from dhuan.pipeline.tasks import predict_grid

        out = predict_grid({})
        assert out["ok"] is False
        assert out["reason"] == "model not trained"
        assert out["predictions"] == []
    finally:
        if saved is not None:
            model.write_bytes(saved)


def test_predict_grid_with_model_writes_predictions(dynamodb: object, env: dict[str, str]) -> None:
    from dhuan.model.predict import load_artifact
    from dhuan.pipeline.tasks import predict_grid

    try:
        artifact = load_artifact()
    except Exception:
        pytest.skip("no trained model artifact")
    assert artifact
    out = predict_grid({})
    assert out["ok"] is True
    assert len(out["predictions"]) > 100
    for p in out["predictions"][:5]:
        assert p["pm25_low"] <= p["pm25_mid"] <= p["pm25_high"]


def test_evaluate_and_publish_alerts_no_subscriptions(
    dynamodb: object, env: dict[str, str]
) -> None:
    from dhuan.pipeline.tasks import evaluate_alerts, publish_alerts

    out = evaluate_alerts({"predictions": []})
    assert out["ok"] is True
    published = publish_alerts({"alerts": []})
    assert published["published"] == 0


def test_lambda_handler_dispatches() -> None:
    from dhuan.pipeline.tasks import lambda_handler

    unknown = lambda_handler({"task": "nope"})
    assert unknown["ok"] is False
    failure = lambda_handler({"task": "failure_recorded", "error": "x"})
    assert failure["failed"] is True

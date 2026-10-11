"""Pipeline task handlers against real containers (LocalStack)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_validate_and_merge_rejects_failures() -> None:
    from dhuan.pipeline.tasks import validate_and_merge

    out = validate_and_merge(
        {
            "ingested": [
                {"feed": "openaq", "records": 3, "ok": True},
                {"feed": "firms", "records": 0, "ok": False},
            ]
        }
    )
    assert out["ok"] is False
    assert out["rejects"][0]["feed"] == "firms"
    assert out["total_records"] == 3


def test_ingest_fires_without_key_is_soft_skip() -> None:
    from dhuan.pipeline.tasks import ingest_fires

    out = ingest_fires({})
    assert out["feed"] == "firms"
    # soft skip: pipeline continues, feed marked not ok
    assert out["ok"] is False


def test_persist_estimates_writes_records(dynamodb: object, env: dict[str, str]) -> None:
    from datetime import UTC, datetime

    from dhuan.pipeline.tasks import persist_estimates
    from dhuan.store.dynamodb import EstimatesStore

    now = datetime.now(UTC)
    out = persist_estimates(
        {
            "predictions": [
                {"cell": "88008990c7fffff", "ts": now.isoformat(),
                 "pm25_low": 100.0, "pm25_mid": 130.0, "pm25_high": 160.0}
            ]
        }
    )
    assert out["written"] == 1
    latest = EstimatesStore().get_latest("88008990c7fffff")
    assert latest is not None
    assert float(latest["pm25_mid"]) == 130.0


def test_failure_recorded_emits_and_returns() -> None:
    from dhuan.pipeline.tasks import failure_recorded

    out = failure_recorded({"error": "boom"})
    assert out["failed"] is True


def test_lambda_handler_unknown_task() -> None:
    from dhuan.pipeline.tasks import lambda_handler

    out = lambda_handler({"task": "nope"})
    assert out["ok"] is False
    assert "unknown task" in out["error"]

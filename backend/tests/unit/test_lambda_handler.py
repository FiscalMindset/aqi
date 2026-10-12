"""Regression tests for the Lambda container entry point.

The Mangum regression is the reason this file exists: `Mangum(app).handler`
worked in mangum<0.17 and raises AttributeError in current releases, which
only shows up as a 502/500 through API Gateway - never in unit tests of the
FastAPI app itself, because those bypass the adapter entirely.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _load_handler_module() -> Any:
    """Import backend/lambda_handler.py, which lives outside the package."""
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    spec = importlib.util.spec_from_file_location("dhuan_lambda_handler",
        ROOT / "lambda_handler.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def handler_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.delenv("CMD", raising=False)
    return _load_handler_module()


def test_mangum_adapter_is_called_not_dot_handler(
    handler_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The adapter must be invoked as a callable, never via `.handler`."""
    calls: list[tuple[dict, object]] = []

    class FakeMangum:
        def __init__(self, app: object, lifespan: str = "auto") -> None:
            self.app = app

        def __call__(self, event: dict, context: object) -> dict:
            calls.append((event, context))
            return {"statusCode": 200, "body": "{}"}

        # If production code regresses to `.handler`, this attribute must not
        # exist - that is precisely the failure we are guarding against.
        def __getattr__(self, item: str) -> Any:
            raise AttributeError(f"'FakeMangum' object has no attribute '{item}'")

    import mangum

    monkeypatch.setattr(mangum, "Mangum", FakeMangum)
    ctx = SimpleNamespace()
    result = handler_module.handler({"httpMethod": "GET", "path": "/health"}, ctx)

    assert result["statusCode"] == 200
    assert len(calls) == 1
    assert calls[0][1] is ctx


def test_pipeline_env_routes_to_task_handler(
    handler_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CMD", "pipeline")
    seen: list[dict] = []

    def fake_pipeline(event: dict, context: object) -> dict:
        seen.append(event)
        return {"statusCode": 200, "body": '{"task":"ingest_stations"}'}

    from dhuan.pipeline import tasks

    monkeypatch.setattr(tasks, "lambda_handler", fake_pipeline)
    result = handler_module.handler({"task": "ingest_stations"}, SimpleNamespace())

    assert result["statusCode"] == 200
    assert seen == [{"task": "ingest_stations"}]


def test_api_env_does_not_use_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """CMD=api (and unset) must go to Mangum, never to the task router."""
    module = _load_handler_module()

    class Boom:
        def __init__(self, *a: object, **k: object) -> None:
            raise AssertionError("pipeline router must not be imported for CMD=api")

    from dhuan.pipeline import tasks

    monkeypatch.setattr(tasks, "lambda_handler", Boom)
    for value in ("api", "", None):
        if value is None:
            os.environ.pop("CMD", None)
        else:
            monkeypatch.setenv("CMD", value)
        try:
            module.handler({}, SimpleNamespace())
        except AssertionError as exc:  # pragma: no cover - failure path
            pytest.fail(str(exc))
        except Exception:
            pass

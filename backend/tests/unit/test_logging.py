"""Unit tests for logging, tracing and metrics (JSON structure + correlation)."""

from __future__ import annotations

import json
import logging

from dhuan.core.config import Settings
from dhuan.core.logging import (
    JsonFormatter,
    correlation_id,
    get_logger,
    log_event,
    new_correlation_id,
)


def test_json_formatter_emits_correlation_id() -> None:
    import io

    stream = io.StringIO()
    test_logger = logging.getLogger("dhuan.test_json")
    test_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    test_logger.addHandler(handler)
    try:
        cid = new_correlation_id()
        log_event(test_logger, logging.INFO, "unit_test_event", extra_field=42)
        payload = json.loads(stream.getvalue().strip())
    finally:
        test_logger.removeHandler(handler)
    assert payload["msg"] == "unit_test_event"
    assert payload["correlation_id"] == cid
    assert payload["extra_field"] == 42
    assert payload["level"] == "INFO"


def test_correlation_id_context_roundtrip() -> None:
    cid = new_correlation_id()
    assert correlation_id.get() == cid
    cid2 = new_correlation_id()
    assert correlation_id.get() == cid2 != cid
    correlation_id.set("")
    assert correlation_id.get() == ""


def test_get_logger_prefixes_module() -> None:
    assert get_logger("x").name == "dhuan.x"


def test_settings_defaults() -> None:
    s = Settings(env="test")
    assert s.demo_mode is False
    assert s.h3_resolution == 8
    assert s.aws_region == "ap-south-1"


def test_settings_demo_flag_coercion() -> None:
    assert Settings(env="test", demo_mode="1").demo_mode is True
    assert Settings(env="test", demo_mode="false").demo_mode is False

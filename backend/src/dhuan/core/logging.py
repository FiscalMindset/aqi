"""Structured JSON logging with a per-request correlation id."""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def new_correlation_id() -> str:
    cid = uuid.uuid4().hex[:16]
    correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    correlation_id.set(cid)


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per line; safe for CloudWatch Logs Insights."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "correlation_id": correlation_id.get(),
        }
        std = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in std and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger("dhuan")
    root.setLevel(level.upper())
    if root.handlers:
        root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"dhuan.{name}")


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    logger.log(level, event, extra=fields)

"""CloudWatch metrics via AWS Lambda Powertools EMF, with a no-op local mode.

`record()` is the single entry point used across the codebase: inside Lambda
it emits embedded metric format; locally and in tests it is a cheap no-op
(enable `DHUAN_DEBUG_METRICS=1` to print).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any


class _EphemeralMetrics:
    """Minimal recorder that works outside Lambda (dev/tests)."""

    namespace = "DhuanDetective/Local"

    def add_metric(self, name: str, unit: str, value: float) -> None:
        if os.getenv("DHUAN_DEBUG_METRICS") == "1":
            print(f"metric {name}={value} {unit}")

    def add_dimension(self, _key: str, _value: str) -> None:
        return None

    @contextmanager
    def single_metric(self, _name: str, _unit: str, **_dimensions: str) -> Iterator[None]:
        yield


@lru_cache
def get_metrics(namespace: str = "DhuanDetective") -> Any:
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        from aws_lambda_powertools import Metrics  # noqa: PLC0415 - only importable inside Lambda

        return Metrics(namespace=namespace)
    return _EphemeralMetrics()


def record(name: str, value: float, unit: str = "Count") -> None:
    get_metrics().add_metric(name=name, unit=unit, value=value)

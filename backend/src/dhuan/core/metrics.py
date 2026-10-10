"""CloudWatch metrics via AWS Lambda Powertools EMF, with a no-op local mode."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

_METRICS_ENV_INITIALISED = False


class _EphemeralMetrics:
    """Minimal metric recorder that works outside Lambda (dev/tests)."""

    def __init__(self) -> None:
        self.namespace = "DhuanDetective/Local"

    def add_metric(self, name: str, unit: str, value: float) -> None:
        if os.getenv("DHUAN_DEBUG_METRICS") == "1":
            print(f"metric {name}={value} {unit}")

    def add_dimension(self, key: str, value: str) -> None:  # noqa: D102
        return None

    @contextmanager
    def single_metric(self, name: str, unit: str, **dimensions: str) -> Iterator[None]:
        yield


def get_metrics(namespace: str = "DhuanDetective") -> Any:
    global _METRICS_ENV_INITIALISED
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        from aws_lambda_powertools import Metrics  # local import: only in Lambda

        return Metrics(namespace=namespace)
    return _EphemeralMetrics()


def record(name: str, value: float, unit: str = "Count") -> None:
    get_metrics().add_metric(name=name, unit=unit, value=value)

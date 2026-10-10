"""X-Ray tracing via AWS Lambda Powertools; a no-op tracer outside Lambda."""

from __future__ import annotations

import contextlib
import os
from functools import lru_cache
from typing import Any


class _NoopTracer:
    """Zero-overhead tracer for local dev and tests."""

    def capture_method(self, func: Any) -> Any:
        return func

    def capture_subsegment(self, *_args: Any, **_kwargs: Any) -> Any:
        return contextlib.nullcontext()

    def put_annotation(self, _key: str, _value: Any) -> None:
        return None

    def put_metadata(self, _key: str, _value: Any) -> None:
        return None


@lru_cache
def get_tracer() -> Any:
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        from aws_lambda_powertools import Tracer  # noqa: PLC0415 - only importable inside Lambda

        return Tracer()
    return _NoopTracer()

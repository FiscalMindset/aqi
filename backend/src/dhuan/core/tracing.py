"""X-Ray tracing via AWS Lambda Powertools; no-op outside Lambda."""

from __future__ import annotations

import os
from typing import Any

_tracer: Any = None


def get_tracer() -> Any:
    global _tracer
    if _tracer is None:
        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            from aws_lambda_powertools import Tracer

            _tracer = Tracer()
        else:

            class _NoopTracer:
                def capture_method(self, func: Any) -> Any:  # noqa: D102
                    return func

                def capture_subsegment(self, *a: Any, **k: Any) -> Any:  # noqa: D102
                    import contextlib

                    return contextlib.nullcontext()

                def put_annotation(self, key: str, value: Any) -> None:  # noqa: D102
                    return None

                def put_metadata(self, key: str, value: Any) -> None:  # noqa: D102
                    return None

            _tracer = _NoopTracer()
    return _tracer

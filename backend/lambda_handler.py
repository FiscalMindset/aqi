"""Single Lambda entry point for the container image.

Two roles, selected by the CMD environment variable:

    CMD=pipeline  -> Step Functions task handlers (dhuan.pipeline.tasks)
    otherwise     -> Mangum adapter for the FastAPI app (dhuan.api.app:app)

SAM builds this image once and reuses it for the API function and the pipeline
function; see infra/template.yaml.
"""

from __future__ import annotations

import os


def handler(event: dict, context: object) -> dict:  # noqa: ANN001, ARG001
    """Route an invocation to the API adapter or a pipeline task."""
    if os.environ.get("CMD", "api").lower() == "pipeline":
        from dhuan.pipeline.tasks import lambda_handler as pipeline_handler

        return pipeline_handler(event, context)

    from mangum import Mangum

    from dhuan.api.app import app

    return Mangum(app, lifespan="off").handler(event, context)
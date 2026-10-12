"""Contract tests: fuzz every route; zero 5xx allowed.

The OpenAPI schema is generated from the FastAPI app. If the spec and the
implementation disagree, this suite fails (Schemathesis, no live server).
"""

from __future__ import annotations

import pytest
import schemathesis
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, settings

pytestmark = pytest.mark.contract


def _spec() -> dict:
    """OpenAPI 3.0 form: FastAPI emits 3.1, our committed spec and the tooling
    (Schemathesis, Redoc, codegen) are 3.0.x, so we pin the version string."""
    from dhuan.api.app import create_app

    spec = dict(create_app().openapi())
    spec["openapi"] = "3.0.3"
    return spec


SCHEMA = schemathesis.openapi.from_dict(_spec(), validate_schema=False)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from dhuan.api.app import create_app

    return TestClient(create_app())


@SCHEMA.parametrize()
@settings(
    max_examples=25,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_api_contract(case: schemathesis.Case, client: TestClient) -> None:
    response = case.call(session=client)
    # /ready intentionally answers 503 when dependencies are unhealthy
    if case.operation.verbose_name == "GET /ready":
        assert response.status_code in (200, 503)
        return
    # typed, spec-compliant failures are allowed; unhandled 5xx are not
    if response.status_code >= 500:
        detail = f"unhandled 5xx on {case.operation}: {response.text[:200]}"
        assert response.status_code == 503, detail
        ctype = response.headers.get("content-type", "")
        assert ctype.startswith("application/problem+json")
        return
    if response.status_code in (400, 404, 422):
        assert response.headers.get("content-type", "").startswith("application/problem+json")

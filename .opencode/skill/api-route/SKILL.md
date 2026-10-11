---
name: add-api-route
description: Add a complete production API route to Dhuan Detective. Use when creating any new /v1 route. Walks the full rule-2 checklist in order: schema, response model, router, error typing, logging/metrics, OpenAPI, unit/integration/contract tests.
---

# Add an API route (complete, not partial)

## Order (copy `estimate.py` as the reference implementation)

1. **Request schema** — `backend/src/dhuan/api/schemas.py`
2. **Response model** — `backend/src/dhuan/api/models.py` with `json_schema_extra` examples
3. **Router** — `backend/src/dhuan/api/routers/<name>.py`
   - `Annotated` validation on every parameter
   - coverage polygon guard → `outside_coverage_problem` (422)
   - store/upstream failure → `upstream_problem` / `not_configured_problem` (503)
   - never a bare `except`
4. **Register** the router in `backend/src/dhuan/api/app.py`
5. **Observability** — one `record("RouteServed", 1)` metric; errors log with the correlation id (automatic via middleware)
6. **Throttling** — add a `MethodSettings` entry in `infra/template.yaml` (stricter for `/v1/explain`)
7. **Tests**
   - unit: respx-mocked upstreams; empty-store cache between tests (`reset_clients()`)
   - integration: real containers, happy path + one failure path
   - contract: covered automatically by Schemathesis once the route exists
8. **Docs** — `openapi.yaml` regeneration (`make openapi`), commit the diff

## Forbidden

- Returning raw dicts without a response model
- Swallowing upstream errors
- Hardcoding sample values
- Adding a route without an integration test

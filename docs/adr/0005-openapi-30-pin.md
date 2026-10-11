# ADR 0005: Pin the committed OpenAPI spec to 3.0.3

## Status
Accepted

## Context
FastAPI 0.143 emits OpenAPI 3.1.0. Schemathesis 3.35 rejects 3.1, and several codegen tools are 3.0-only.

## Decision
The contract test loads the app spec and rewrites the version string to 3.0.3 before handing it to Schemathesis; the committed `openapi/openapi.yaml` is 3.0.3. The CI drift job regenerates and diffs the committed file.

## Consequences
- Contract fuzzing works.
- Redoc/Swagger/codegen consume the same spec.
- If FastAPI emits 3.1-only constructs later, the pin needs revisiting.

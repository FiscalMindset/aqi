---
name: data-source
description: Add a new external data source to Dhuan Detective. Use when integrating any new upstream feed. Enforces documentation-first verification, dedicated client with timeouts/retries, freshness tracking, licence entry in docs, and tests with recorded fixtures.
---

# Add a data source

## 1. Verify first (rule 5)

- Read the provider's current official docs. Confirm: endpoint, auth header, rate limits, schema, units, timezone.
- Record it in `docs/DATA_SOURCES.md`: source, licence, attribution, rate limits, auth, **verified date**.
- If the docs contradict memory, the docs win.

## 2. Client (`backend/src/dhuan/ingest/<name>.py`)

- `UpstreamClient`/`make_client` from `core/http.py` for timeout + backoff + jitter + metrics.
- Typed records in `ingest/types.py` carrying provenance (source + observed time).
- Missing credentials → `NotConfiguredError` (never a fabricated fallback).
- Rate limits → respect them; document the client's cadence.

## 3. Freshness

- The service layer wraps reads in `TTLCache.get_or_fetch` so upstream outages serve the last good value with `data_age_seconds` and `stale`.
- `FeedsStore.record_success/record_failure` at the pipeline boundary so `/v1/status` is honest.

## 4. Tests

- Record real responses into `backend/tests/fixtures/` with a provenance block (like `openmeteo_forecast_sample.json`).
- `respx`-mock every test: URL, params and headers pinned, so a silent upstream change fails the build.
- One test proving the client refuses to serve without credentials.

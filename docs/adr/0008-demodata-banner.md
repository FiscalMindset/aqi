# ADR 0008: Demo data via a recorded snapshot + permanent banner

## Status
Accepted

## Context
The brief allows `DEMO_MODE=1` to serve recorded data with a permanent visible banner, defaulting to off. The build environment has no OpenAQ API key and no AWS credentials.

## Decision
Recorded data is real (OpenAQ public archive, fetch provenance recorded) and lives under `fixtures/demo/`. The API marks every demo response with `X-Dhuan-Demo: 1` AND `demo_mode: true`; the frontend banner renders while `document.documentElement.dataset.demo === "1"`. The header is exposed through CORS so cross-origin frontends can read it.

## Consequences
- Demo mode is never mistaken for live data.
- The default is off; the flag is explicit in every response.

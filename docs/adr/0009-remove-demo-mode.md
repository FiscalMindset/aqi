# 0009 - Remove demo mode; real feeds only

- Status: accepted
- Date: 2026-10-12
- Supersedes: [0008](0008-demodata-banner.md)

## Context

ADR 0008 added `DEMO_MODE` because the build environment had no OpenAQ API key
and no AWS credentials, so there was no way to serve anything at all.

Two things changed that make it the wrong design now.

First, the OpenAQ **public archive** needs no credential. It is a set of daily
files on OpenAQ's public bucket, and it is where the 591k-row training snapshot
already came from. `ingest/archive.py` distils it into a compact per-station
index that ships in the image: 73 real stations, 165 KB, 48 hours of history
each.

Second, `data/delhi_sources.json` already ships 2,329 classified OSM features
from a real Overpass extract, so upwind attribution no longer needs OpenSearch
to be running.

## Decision

`DEMO_MODE`, the `demo_mode` field on every response, the `X-Dhuan-Demo`
header, the frontend banner, `api/demo.py` and `fixtures/demo/` are deleted.

Each feed now has two real sources:

| Feed | Preferred | Fallback | Honesty mechanism |
|---|---|---|---|
| Stations | OpenAQ v3 API (needs key) | OpenAQ public archive | true `data_age_seconds`, `stale` beyond 36h |
| Sources | OpenSearch (needs service) | shipped OSM catalogue | `sources_unavailable` when neither is present |

If no source can answer, the route returns a typed RFC 9457 Problem. There is no
path left that can return a plausible-looking number that was not measured.

## Consequences

- Rule 1 becomes structural. There is no flag to forget to turn off, so a
  deployment cannot accidentally serve recorded data as if it were live.
- The product runs with no third-party credentials at all.
- Station readings can be days old, so the UI must show the age prominently.
  That is a feature: an 89-hour-old reading labelled as current would be the
  dishonest outcome, and now it cannot happen.
- Demo fixtures can no longer be used to smoke-test a deployment. `make test`
  covers that with the container-backed suite instead.

## Related

The explanation path was built in the same period
([ADR 0010](0010-grounded-explanation.md)): Groq may reword an
already-grounded answer but may never introduce a number, and the deterministic
composer serves the explanation whenever Groq is unavailable or unfaithful.
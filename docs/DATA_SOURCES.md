# Data sources

| Source | Used for | Auth | Rate limit | Licence / attribution | Verified |
|---|---|---|---|---|---|
| OpenAQ v3 API | Live station readings | `X-API-Key` (free) | 60/min, 2000/hour | CC BY 4.0 — attribution "OpenAQ" | 2026-10-15 |
| OpenAQ public S3 archive | Training history, demo snapshot | none | — | CC BY 4.0 | 2026-10-15 |
| Open-Meteo forecast + archive | Weather features | none | fair use | CC BY 4.0 — © Open-Meteo | 2026-10-15 |
| NASA FIRMS | Active-fire detections | `MAP_KEY` (free) | 5000 / 10 min | NASA FIRMS | 2026-10-15 |
| OpenStreetMap (Overpass) | Source geography | none | fair use; contact UA required | ODbL 1.0 — © OpenStreetMap contributors | 2026-10-15 |
| CPCB National AQI doc | AQI category breakpoints | none | — | Central Pollution Control Board, India | 2026-10-15 |
| Amazon Location Service (optional) | Map tiles, routes | AWS IAM | service limits | AWS service | planned |

Notes:
- The Open-Meteo **historical** host is `archive-api.open-meteo.com` (the `archive.` hostname fails DNS from some networks).
- Overpass: use global mirrors only (`overpass-api.de`, `overpass.private.coffee`, `overpass.kumi.systems`). Regional mirrors (osm.ch, osm.jp) serve national extracts and return zero elements for Delhi. A contact User-Agent is mandatory.
- OpenAQ v1/v2 were retired 2025-01-31 (HTTP 410).

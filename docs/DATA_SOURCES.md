# Data sources

| Source | Used for | Auth | Rate limit | Licence / attribution | Verified |
|---|---|---|---|---|---|
| OpenAQ v3 API | Live station readings | `X-API-Key` (free) | 60/min, 2000/hour | CC BY 4.0 — attribution "OpenAQ" | 2026-10-15 |
| OpenAQ public S3 archive | Training history, demo snapshot | none | — | CC BY 4.0 | 2026-10-15 |
| Open-Meteo forecast + archive | Weather features | none | fair use | CC BY 4.0 — © Open-Meteo | 2026-10-15 |
| NASA FIRMS | Active-fire detections | `MAP_KEY` (free, email signup) | 5000 / 10 min | NASA FIRMS | 2026-10-14 |
| Open-Meteo Air Quality | Independent PM2.5 / AQI cross-check | **none** | fair use | CC BY 4.0 — © Open-Meteo, data © CAMS | 2026-10-14 |
| OpenStreetMap (Overpass) | Source geography | none | fair use; contact UA required | ODbL 1.0 — © OpenStreetMap contributors | 2026-10-15 |
| CPCB National AQI doc | AQI category breakpoints | none | — | Central Pollution Control Board, India | 2026-10-15 |
| Amazon Location Service (optional) | Map tiles, routes | AWS IAM | service limits | AWS service | planned |

Notes:
- **NASA FIRMS has no keyless path.** `MAP_KEY` is free (email signup only) but required for the area/hotspot endpoint; the limit is 5000 transactions per 10 minutes. Verified live 2026-10-14: the key works and returns valid CSV, and the Delhi-NCR bbox legitimately returned **zero** detections over a 5-day window while Punjab returned 5 real detections with FRP and confidence. Zero fires is a result, not a failure.
- **Open-Meteo Air Quality** (`air-quality-api.open-meteo.com/v1/air-quality`) is CAMS re-served and needs **no credential**. It is a regional aerosol grid, **not** a ground reading and **not** fire detection. Its `dust` variable must never be presented as wildfire smoke: measured for Delhi on 2026-10-14 it read ~102 µg/m³ during post-monsoon dust season, so treating it as smoke would be a confident fabrication. Used only as a cross-check beside the station-anchored estimate.
- The Open-Meteo **historical** host is `archive-api.open-meteo.com` (the `archive.` hostname fails DNS from some networks).
- Overpass: use global mirrors only (`overpass-api.de`, `overpass.private.coffee`, `overpass.kumi.systems`). Regional mirrors (osm.ch, osm.jp) serve national extracts and return zero elements for Delhi. A contact User-Agent is mandatory.
- OpenAQ v1/v2 were retired 2025-01-31 (HTTP 410).

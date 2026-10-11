# Demo script (3 minutes)

Rehearse once, then run it live. Everything below uses the real system in demo mode (recorded real data, banner visible — say so when asked).

## 0:00–0:30 — The problem

> "Delhi has ~40 official monitoring stations for 30 million people. Most neighbourhoods have no reading at all, and even where one exists, a number doesn't tell you *why*. Dhuan Detective answers: why is the air bad on my street right now, and what should I do?"

Show the explorer: estimate with the 80% interval, the nearest official station beside it, and the "Estimate, not a measurement" note.

## 0:30–2:00 — Live walkthrough (real data)

1. Search "Rohini" (or drop a pin). Point at:
   - the estimate + interval + CPCB category chip,
   - the map: wind arrow, source markers with labels (Ghazipur, Bhalswa — real OSM names),
   - the upwind cone logic on `/how-it-works`.
2. Click **"Why is the air bad here?"**. The agent trace appears with the real tool calls:
   `get_station_context`, `get_air_and_wind`, `get_model_estimate`, `find_upwind_sources`, `get_recent_fires`.
3. Show the ranked likely causes with the evidence behind each, and the three persona cards.

## 2:00–2:30 — The real validation number

Open `/methodology`: the measured holdout numbers (MAE 26.1 vs persistence baseline 24.9), the conformal interval coverage 0.800, and the honest sentence: **the nearest-station baseline ships when it wins, and the UI says which producer served each number.**

## 2:30–3:00 — Where each AWS service does real work

Walk `docs/AWS.md` on screen:

| Service | Job in the demo |
|---|---|
| Bedrock + Strands | the agent that explained the causes (scripted fallback in demo mode is stated) |
| OpenSearch | the geo query that found the landfills |
| Step Functions + EventBridge | the hourly pipeline that produced the grid |
| DynamoDB | the estimates table with TTL |
| S3 + CloudFront | serving this web app |
| SNS | the alerts subscribers get |

Close with the honest limitations from the model card.

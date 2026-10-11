---
name: ml
description: Machine-learning skill for Dhuan Detective. Use when changing features, training, evaluation, prediction, the conformal interval, or the model card. Enforces the leakage policy, the leave-one-station-out + temporal holdout protocol, the baseline comparison, and the hand-computed-numbers-only rule for metrics.
---

# ML skill

## When to use

Any change under `backend/src/dhuan/model/`, `scripts/fetch_training_data.py`, or the generated `docs/MODEL_CARD.md`.

## Leakage policy (asserted by tests)

- The label is the station's own PM2.5 at hour *t*.
- Features may use: calendar at *t*, weather at *t*, static geography of the prediction point, and the nearest station's history **strictly before** *t*.
- No feature may name or encode the target station's current value. A test builds a 2-row snapshot and asserts `station_lag1` is the earlier hour.

## Training protocol

1. `uv run python scripts/fetch_training_data.py` → snapshot with sha256.
2. `uv run python -m dhuan.model.train` → three quantile models + conformal radius + metrics.
3. `uv run python -m dhuan.model.evaluate` → regenerates `docs/MODEL_CARD.md` from `metrics.json`.
4. Commit `metrics.json` + the model card together; the snapshot hash ties data to metrics.

## Evaluation must report

- MAE, RMSE, R², bias, 80% coverage, mean interval width.
- Overall **and** per AQI band.
- Temporal holdout **and** leave-one-station-out.
- Baselines: global mean, per-station climatology, persistence (lag-1h).
- The winner by the documented rule (MAE) — currently `nearest-station-baseline (persistence-lag1h)`; the card and the UI must say so.

## The interval

Raw p10/p90 under-cover (measured 0.707). Split-conformal radius = the 0.8-quantile of |y − median| on the holdout (28.65 µg/m³ → measured coverage 0.800). Report both raw and calibrated coverage.

## Honesty rules

- Model-card numbers come from `metrics.json` only. Never type a metric by hand.
- The UI must state which producer served each number (`served_by`).
- If the model does not beat the baseline, ship the better one and label it.

## Test gates

```bash
uv run pytest tests/model -q     # leakage, coverage tolerance, baseline regression
```

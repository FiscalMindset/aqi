# ADR 0003: Ship the better of model vs nearest-station baseline

## Status
Accepted

## Context
Leave-one-station-out and temporal-holdout evaluation shows persistence (lag-1h) beats the model on MAE (24.9 vs 26.1 µg/m³) while losing on RMSE. The brief: if the model is not meaningfully better, say so and ship the better one.

## Decision
Decision rule = temporal-holdout MAE. The API's `served_by` field labels every number as produced by the model or the nearest-station baseline. Near a station the persistence value is served; away from stations the model is served with its measured error.

## Consequences
- Users always see which producer made the number, with the comparison published on `/methodology`.
- The model card states the comparison explicitly.
- Future improvements must beat the baseline to become the default; the test asserts the `winner` field is consistent with the rule.

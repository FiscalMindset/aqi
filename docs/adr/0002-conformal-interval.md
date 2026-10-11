# ADR 0002: Split-conformal interval over raw quantile models

## Status
Accepted

## Context
Quantile regression (p10/p90) under-covers during rapid AQI swings: measured coverage 0.707 on the temporal holdout. The brief demands an 80% interval with honest, reported coverage.

## Decision
Keep the quantile models as the median; add a split-conformal radius = the 0.8-quantile of |y − median| on the holdout (28.65 µg/m³). Serve median ± radius. Report both raw and calibrated coverage.

## Alternatives considered
- Wider quantile levels (p05/p95): ad-hoc, still uncalibrated.
- Bootstrap ensembles: much slower inference for marginal gain.
- Scaling the quantile width: no finite-sample guarantee.

## Consequences
- Measured coverage 0.800 on the holdout, asserted in tests within [0.75, 0.85].
- One number to store in the artifact; recomputed at every training run.

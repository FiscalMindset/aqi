# ADR 0001: H3 resolution 8 for the grid

## Status
Accepted

## Context
The product needs a grid dense enough to distinguish "my street" from "the next neighbourhood", small enough that an hourly pipeline over the whole NCR fits in Lambda memory and DynamoDB budget.

## Decision
H3 resolution 8 (~0.74 km² average cell area, ~460 m edge). Derive the cell set deterministically from the real OSM NCR boundary polygons with a 0.004° sampling grid.

## Alternatives considered
- **Res 9** (~0.1 km²): 6× more cells; pipeline memory and DynamoDB writes grow 6×; street-level claims would still exceed the model's resolution.
- **Res 7** (~5 km²): too coarse to distinguish neighbouring localities.
- **Regular lat/lon grid**: simpler but poor hex packing and worse neighbour analysis.

## Consequences
- Deterministic grid → exact counts are pinned in tests.
- The model operates at ~0.74 km² granularity, matching what the training data can actually resolve.

"""Backfill historical estimates into DynamoDB from the recorded snapshot.

Lets the explorer show a real 24-hour history before the first pipeline run.

Usage: PYTHONPATH=backend/src DEMO_MODE=1 uv run --project backend python scripts/backfill.py --hours 48
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from dhuan.core.config import get_settings
from dhuan.geo.grid import cell_center, grid_cells
from dhuan.model.features import build_feature_row, static_features
from dhuan.model.predict import (
    load_artifact,
    predict_from_frame,
    static_sources_default,
)
from dhuan.store.dynamodb import EstimatesStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=48)
    args = parser.parse_args()

    try:
        artifact = load_artifact()
    except Exception as exc:  # noqa: BLE001
        print(f"no model artifact ({exc}); run `make train` first")
        return 2

    settings = get_settings()
    cells = grid_cells(settings.h3_resolution)
    sources = static_sources_default()
    store = EstimatesStore()

    # the recorded station anchor (real Delhi data) supplies lag features
    from dhuan.api.demo import latest_recorded_reading

    anchor = latest_recorded_reading()
    anchor_value = anchor.value if anchor else 150.0

    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    written = 0
    for h in range(args.hours, 0, -1):
        ts = now - timedelta(hours=h)
        for cell in cells[:200]:  # bounded per run; raise for a full backfill
            center = cell_center(cell)
            feats = build_feature_row(
                ts=ts,
                lat=center.lat,
                lon=center.lon,
                weather_row={
                    "wind_speed": 2.5,
                    "wind_gust": 4.0,
                    "temp_c": 18.0,
                    "rh": 70.0,
                    "precip": 0.0,
                    "wind_dir": 292.0,
                },
                static_feats=static_features(center, sources),
                station_lag1=anchor_value,
                station_lag24=anchor_value,
                station_rolling6=anchor_value,
            )
            pred = predict_from_frame(feats, artifact)
            store.put_estimate(
                cell, ts, pred.pm25_low, pred.pm25_mid, pred.pm25_high, "backfill"
            )
            written += 1
    print(f"backfilled {written} estimates over {args.hours} hours")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

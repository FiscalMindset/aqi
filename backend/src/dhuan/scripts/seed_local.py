"""Local/dev seeding entry point: OSM sources and DynamoDB tables.

Usage:
    uv run python -m dhuan.scripts.seed_local --all
    uv run python -m dhuan.scripts.seed_local --sources
    uv run python -m dhuan.scripts.seed_local --tables

Works against LocalStack (AWS_ENDPOINT_URL) and against a real deployment.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FIXTURE = Path(__file__).resolve().parents[3] / "data" / "static_sources" / "station_8118.json"

KeySchema = list[dict[str, str]]
AttrDefs = list[dict[str, str]]


def _schema(pk: str, sk: str | None = None, gsi: str | None = None) -> tuple[KeySchema, AttrDefs]:
    """Build a KeySchema and matching AttributeDefinitions for a table."""
    key_schema: KeySchema = [{"AttributeName": pk, "KeyType": "HASH"}]
    attrs: AttrDefs = [{"AttributeName": pk, "AttributeType": "S"}]
    if sk:
        key_schema.append({"AttributeName": sk, "KeyType": "RANGE"})
        attrs.append({"AttributeName": sk, "AttributeType": "S"})
    if gsi:
        attrs.append({"AttributeName": gsi, "AttributeType": "S"})
    return key_schema, attrs


def seed_tables() -> int:
    """Create the three DynamoDB tables and the subscriptions locality GSI."""
    from dhuan.core.config import get_settings
    from dhuan.store.dynamodb import dynamodb_client

    client = dynamodb_client()
    settings = get_settings()
    tables: dict[str, tuple[KeySchema, AttrDefs]] = {
        settings.dynamodb_table_estimates: _schema("pk", sk="sk"),
        settings.dynamodb_table_feeds: _schema("pk"),
        settings.dynamodb_table_subscriptions: _schema("pk"),
    }
    existing = set(client.list_tables().get("TableNames", []))
    for name, (key_schema, attrs) in tables.items():
        if name in existing:
            print(f"exists {name}")
            continue
        client.create_table(
            TableName=name,
            KeySchema=key_schema,
            AttributeDefinitions=attrs,
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"created {name}")

    sub = settings.dynamodb_table_subscriptions
    try:
        client.update_table(
            TableName=sub,
            AttributeDefinitions=[{"AttributeName": "locality", "AttributeType": "S"}],
            GlobalSecondaryIndexUpdates=[
                {
                    "Create": {
                        "IndexName": "locality-index",
                        "KeySchema": [{"AttributeName": "locality", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                }
            ],
        )
        print(f"gsi locality-index ensured on {sub}")
    except Exception as exc:
        print(f"gsi: {exc}")
    return 0


def _snapshot_timestamp(payload: dict[str, Any]) -> str:
    """Derive an ISO-8601 `last_seen` from the extract's own metadata."""
    meta = payload.get("metadata") or {}
    for key in ("fetched_at", "generated_at", "timestamp"):
        value = meta.get(key)
        if isinstance(value, str) and value:
            return value
    stamp = datetime.now(UTC).isoformat()
    print(f"extract has no timestamp metadata; using now ({stamp})")
    return stamp


def seed_sources() -> int:
    """Index the committed OSM extract (real Overpass data) into OpenSearch."""
    from dhuan.ingest.osm import parse_overpass
    from dhuan.store.opensearch import SourceIndex

    if not FIXTURE.exists():
        print(f"no local OSM extract at {FIXTURE}; run scripts/fetch_static_features.py first")
        return 2
    payload: Any = json.loads(FIXTURE.read_text())
    # last_seen must be an ISO-8601 timestamp (OpenSearch maps it as a date field),
    # not a label: the extract is historical, so use the snapshot date.
    fetched_at = _snapshot_timestamp(payload)
    docs = [d.to_index_dict() for d in parse_overpass(payload, fetched_at)]
    index = SourceIndex()
    index.ensure_index()
    count = index.bulk_index(docs)
    print(f"seeded {count} sources into {index.index}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true")
    group.add_argument("--sources", action="store_true")
    group.add_argument("--tables", action="store_true")
    args = parser.parse_args()
    code = 0
    if args.tables or args.all:
        code = max(code, seed_tables())
    if args.sources or args.all:
        code = max(code, seed_sources())
    return code


if __name__ == "__main__":
    raise SystemExit(main())

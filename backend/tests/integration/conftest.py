"""Integration fixtures: real OpenSearch + LocalStack (DynamoDB, S3).

Runs with `make test-backend` / docker-compose.test.yml:
  OpenSearch :9201, LocalStack :4567 (ap-south-1).
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import boto3
import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _isolated_aws_config(tmpdir: str) -> tuple[str, str]:
    """Empty AWS config files so no real ~/.aws state leaks into tests."""
    cfg = Path(tmpdir) / "config"
    creds = Path(tmpdir) / "credentials"
    cfg.write_text("")
    creds.write_text("")
    return str(cfg), str(creds)


@pytest.fixture(scope="session")
def env() -> Iterator[dict[str, str]]:
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file, creds_file = _isolated_aws_config(tmpdir)
        settings = {
            "ENV": "test",
            "AWS_REGION": "ap-south-1",
            # LocalStack dummy credentials: avoids the aws-login provider
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "AWS_ENDPOINT_URL": "http://localhost:4567",
            "AWS_CONFIG_FILE": config_file,
            "AWS_SHARED_CREDENTIALS_FILE": creds_file,
            "OPENSEARCH_ENDPOINT": "http://localhost:9201",
            "OPENSEARCH_INDEX": "sources",
            "DYNAMODB_TABLE_ESTIMATES": "test-dhuan-estimates",
            "DYNAMODB_TABLE_FEEDS": "test-dhuan-feeds",
            "DYNAMODB_TABLE_SUBSCRIPTIONS": "test-dhuan-subscriptions",
            "S3_BUCKET": "test-dhuan-artifacts",
            "DEMO_DATA_DIR": str(REPO_ROOT / "fixtures" / "demo"),
            "MODEL_VERSION": "test-v1",
        }
        for k, v in settings.items():
            os.environ[k] = v
        from dhuan.core import config

        config.get_settings.cache_clear()
        yield settings
        config.get_settings.cache_clear()


@pytest.fixture(scope="session")
def dynamodb(env: dict[str, str]) -> Iterator[Any]:
    client = boto3.client(
        "dynamodb", endpoint_url=env["AWS_ENDPOINT_URL"], region_name=env["AWS_REGION"]
    )
    tables = [
        (
            env["DYNAMODB_TABLE_ESTIMATES"],
            [
                {
                    "AttributeName": "pk",
                    "KeyType": "HASH",
                },
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
        ),
        (env["DYNAMODB_TABLE_FEEDS"], [{"AttributeName": "pk", "KeyType": "HASH"}]),
        (env["DYNAMODB_TABLE_SUBSCRIPTIONS"], [{"AttributeName": "pk", "KeyType": "HASH"}]),
    ]
    existing = set(client.list_tables().get("TableNames", []))
    for name, schema in tables:
        if name not in existing:
            client.create_table(
                TableName=name,
                KeySchema=schema,
                AttributeDefinitions=[
                    {"AttributeName": s["AttributeName"], "AttributeType": "S"} for s in schema
                ],
                BillingMode="PAY_PER_REQUEST",
            )
    waiter = client.get_waiter("table_exists")
    for name, _ in tables:
        waiter.wait(TableName=name)
    # subscriptions table needs its locality GSI for by_locality queries
    sub_table = env["DYNAMODB_TABLE_SUBSCRIPTIONS"]
    try:
        client.update_table(
            TableName=sub_table,
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
    except Exception as exc:  # may already exist from a prior run
        print(f"gsi: {exc}")
    yield client
    for name, _ in tables:
        client.delete_table(TableName=name)


@pytest.fixture()
def s3(env: dict[str, str]) -> Iterator[Any]:
    client = boto3.client("s3", endpoint_url=env["AWS_ENDPOINT_URL"], region_name=env["AWS_REGION"])
    bucket = env["S3_BUCKET"]
    try:
        client.create_bucket(
            Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": env["AWS_REGION"]}
        )
    except client.exceptions.BucketAlreadyOwnedByYou:
        pass
    yield client
    objects = client.list_objects_v2(Bucket=bucket).get("Contents", [])
    for o in objects:
        client.delete_object(Bucket=bucket, Key=o["Key"])
    client.delete_bucket(Bucket=bucket)


@pytest.fixture()
def source_index(env: dict[str, str]) -> Iterator[Any]:
    """OpenSearch index seeded with the real Delhi landfill fixture data."""
    from dhuan.store.opensearch import SourceIndex

    index = SourceIndex()
    index.ensure_index()
    payload = json.loads((FIXTURES / "overpass_sample.json").read_text())
    from dhuan.ingest.osm import parse_overpass

    docs = parse_overpass(payload, "2026-10-15T00:00:00+00:00")
    index.bulk_index([d.to_index_dict() for d in docs])
    index.es.indices.refresh(index=index.index)
    yield index
    try:
        index.es.indices.delete(index=index.index)
    except Exception:  # index may not exist in a failure run
        pass
    index.close()

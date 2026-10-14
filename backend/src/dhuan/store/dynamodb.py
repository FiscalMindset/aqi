"""DynamoDB access layer.

Tables (defined in infra/template.yaml, on-demand + PITR):
  estimates      pk cell#<h3>   sk ts#<iso>   TTL 90d
  feeds          pk feed=<name>              single row per feed
  subscriptions  pk sub#<id>                 GSI locality-index on locality

LocalStack is supported through `AWS_ENDPOINT_URL`; nothing here reads real
credentials in dev. In Lambda the default boto3 credential chain applies.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config

from dhuan.core.config import Settings, get_settings
from dhuan.core.logging import get_logger
from dhuan.ingest.types import FeedStatus

logger = get_logger("store.dynamodb")

ESTIMATES_TTL_DAYS = 90


def _dec(value: float | int) -> Decimal:
    """DynamoDB stores numbers as Decimal; float serialisation raises TypeError."""
    return Decimal(str(value))


def _client_config() -> Config:
    return Config(
        retries={"max_attempts": 3, "mode": "standard"},
        connect_timeout=3,
        read_timeout=10,
    )


def dynamodb_resource(settings: Settings | None = None) -> Any:
    s = settings or get_settings()
    kwargs: dict[str, Any] = {
        "region_name": s.aws_region,
        "config": _client_config(),
    }
    if s.aws_endpoint_url:
        kwargs["endpoint_url"] = s.aws_endpoint_url
    return boto3.resource("dynamodb", **kwargs)


def dynamodb_client(settings: Settings | None = None) -> Any:
    s = settings or get_settings()
    kwargs: dict[str, Any] = {"region_name": s.aws_region, "config": _client_config()}
    if s.aws_endpoint_url:
        kwargs["endpoint_url"] = s.aws_endpoint_url
    return boto3.client("dynamodb", **kwargs)


class EstimatesStore:
    """Hourly PM2.5 estimates per H3 cell with a TTL."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.table_name = self.settings.dynamodb_table_estimates
        self._db = dynamodb_resource(self.settings)
        self.table = self._db.Table(self.table_name)

    def put_estimate(  # noqa: PLR0917 - estimate fields stay positional
        self, cell: str, ts: datetime, pm25_low: float, pm25_mid: float, pm25_high: float,
        model_version: str, extra: dict[str, Any] | None = None,
    ) -> None:
        item: dict[str, Any] = {
            "pk": f"cell#{cell}",
            "sk": f"ts#{ts.isoformat()}",
            "cell": cell,
            "ts": ts.isoformat(),
            "pm25_low": _dec(round(pm25_low, 2)),
            "pm25_mid": _dec(round(pm25_mid, 2)),
            "pm25_high": _dec(round(pm25_high, 2)),
            "model_version": model_version,
            "ttl": int((ts + timedelta(days=ESTIMATES_TTL_DAYS)).timestamp()),
        }
        if extra:
            item.update(extra)
        self.table.put_item(Item=item)

    def get_latest(self, cell: str) -> dict[str, Any] | None:
        resp = self.table.query(
            KeyConditionExpression=Key("pk").eq(f"cell#{cell}"),
            ScanIndexForward=False,
            Limit=1,
        )
        items: list[dict[str, Any]] = resp.get("Items", [])
        return items[0] if items else None

    def get_history(self, cell: str, hours: int = 24) -> list[dict[str, Any]]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        resp = self.table.query(
            KeyConditionExpression=(
                Key("pk").eq(f"cell#{cell}") & Key("sk").gte(f"ts#{since.isoformat()}")
            ),
            ScanIndexForward=True,
        )
        return list(resp.get("Items", []))


class FeedsStore:
    """Per-feed freshness records, surfaced verbatim by /v1/status."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._db = dynamodb_resource(self.settings)
        self.table = self._db.Table(self.settings.dynamodb_table_feeds)

    def record_success(self, feed: str, records: int = 0) -> None:
        self.table.put_item(
            Item={
                "pk": f"feed={feed}",
                "ok": True,
                "last_success_at": datetime.now(UTC).isoformat(),
                "last_error": None,
                "records_last_run": records,
            }
        )

    def record_failure(self, feed: str, error: str) -> None:
        self.table.update_item(
            Key={"pk": f"feed={feed}"},
            UpdateExpression="SET ok = :ok, last_error = :err, last_failure_at = :now",
            ExpressionAttributeValues={
                ":ok": False,
                ":err": error,
                ":now": datetime.now(UTC).isoformat(),
            },
        )

    def all(self) -> list[FeedStatus]:
        resp = self.table.scan()
        out: list[FeedStatus] = []
        for item in resp.get("Items", []):
            out.append(_feed_status_from_item(item))
        return out


def _feed_status_from_item(item: dict[str, Any]) -> FeedStatus:
    last_success = item.get("last_success_at")
    return FeedStatus(
        feed=item.get("pk", "").replace("feed=", ""),
        ok=bool(item.get("ok", False)),
        last_success_at=datetime.fromisoformat(last_success) if last_success else None,
        last_error=item.get("last_error"),
        records_last_run=int(item.get("records_last_run", 0)),
    )


class SubscriptionsStore:
    """Email alert subscriptions, idempotent by (email, locality)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._db = dynamodb_resource(self.settings)
        self.table = self._db.Table(self.settings.dynamodb_table_subscriptions)

    @staticmethod
    def make_id(email: str, locality: str) -> str:
        import hashlib

        raw = f"{email.strip().lower()}|{locality.strip().lower()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def create(  # noqa: PLR0917 - subscription fields stay positional
        self,
        email: str,
        locality: str,
        lat: float,
        lon: float,
        threshold_category: str,
        confirmed: bool = False,
        pending_token: str | None = None,
        unsubscribe_token: str | None = None,
    ) -> str:
        sub_id = self.make_id(email, locality)
        now = datetime.now(UTC)
        self.table.put_item(
            Item={
                "pk": f"sub#{sub_id}",
                "email": email.strip().lower(),
                "locality": locality.strip(),
                "lat": _dec(lat),
                "lon": _dec(lon),
                "threshold_category": threshold_category,
                "confirmed": confirmed,
                "created_at": now.isoformat(),
                # hysteresis bookkeeping
                "last_band": None,
                "last_alerted_at": None,
                "pending_token": pending_token,
                # token embedded in the unsubscribe link inside every alert email
                "unsubscribe_token": unsubscribe_token,
            },
            ConditionExpression="attribute_not_exists(pk)",
        )
        return sub_id

    def get(self, sub_id: str) -> dict[str, Any] | None:
        resp = self.table.get_item(Key={"pk": f"sub#{sub_id}"})
        item: dict[str, Any] | None = resp.get("Item")
        return item

    def get_by_unsubscribe_token(self, token: str) -> dict[str, Any] | None:
        """Find a subscription by the token embedded in an alert email.

        Scans rather than using the GSI because the token is a random secret, not
        a partition key we can derive from a query.
        """
        from boto3.dynamodb.conditions import Attr

        resp = self.table.scan(
            FilterExpression=Attr("unsubscribe_token").eq(token),
            Limit=1,
            ProjectionExpression="pk",
        )
        items = resp.get("Items") or []
        if not items:
            return None
        pk = str(items[0]["pk"])
        return self.get(pk[len("sub#") :])

    def confirm(self, sub_id: str) -> None:
        self.table.update_item(
            Key={"pk": f"sub#{sub_id}"},
            UpdateExpression="SET confirmed = :c",
            ExpressionAttributeValues={":c": True},
        )

    def update_alert_state(self, sub_id: str, band: str | None, alerted_at: str | None) -> None:
        self.table.update_item(
            Key={"pk": f"sub#{sub_id}"},
            UpdateExpression="SET last_band = :b, last_alerted_at = :t",
            ExpressionAttributeValues={":b": band, ":t": alerted_at},
        )

    def delete(self, sub_id: str) -> None:
        self.table.delete_item(Key={"pk": f"sub#{sub_id}"})

    def all_subscriptions(self) -> list[dict[str, Any]]:
        """Every stored subscription, confirmed or not.

        The alert evaluator used to query the GSI for the literal locality
        "delhi-ncr", which is not what anybody subscribes under - subscriptions
        are stored as the name the reader typed, e.g. "Ghevra". The query
        therefore always returned nothing and no alert was ever evaluated.
        Scanning by primary key is correct here: the table is small (one row per
        subscriber-locality pair) and a scan needs no index.
        """
        items: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {}
        while True:
            resp = self.table.scan(**kwargs)
            items.extend(resp.get("Items", []))
            last = resp.get("LastEvaluatedKey")
            if not last:
                break
            kwargs["ExclusiveStartKey"] = last
        return items

    def by_locality(self, locality: str) -> Iterable[dict[str, Any]]:
        resp = self.table.query(
            IndexName="locality-index",
            KeyConditionExpression=Key("locality").eq(locality),
        )
        items: list[dict[str, Any]] = resp.get("Items", [])
        return items


def feeds_store(settings: Settings | None = None) -> FeedsStore:
    return FeedsStore(settings)


__all__ = [
    "EstimatesStore",
    "FeedsStore",
    "SubscriptionsStore",
    "dynamodb_client",
    "dynamodb_resource",
    "feeds_store",
]

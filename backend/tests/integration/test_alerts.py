"""Alert-engine tests: evaluation, dedupe, quiet hours, SNS via LocalStack."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

import pytest

from dhuan.alerts.alerts import (
    SnsAlerter,
    compose_message,
    dedupe_message_key,
    evaluate_subscriptions,
    in_quiet_hours,
)
from dhuan.core.config import Settings

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def sns_settings(env: dict[str, str]) -> Settings:
    return Settings(env="test", sns_topic_arn="")


def test_alerter_unconfigured_returns_empty_message_id(sns_settings: Settings) -> None:
    alerter = SnsAlerter(sns_settings)
    assert alerter.configured() is False
    message_id = alerter.publish(
        locality="rohini", email="a@b.c", subject="s", body="b"
    )
    assert message_id == ""


def test_alerter_publishes_with_topic(sns_settings: Settings, env: dict[str, str]) -> None:
    import boto3

    client = boto3.client(
        "sns", endpoint_url=env["AWS_ENDPOINT_URL"], region_name=env["AWS_REGION"]
    )
    topic = client.create_topic(Name="test-dhuan-alerts")["TopicArn"]
    settings = Settings(env="test", sns_topic_arn=topic)
    alerter = SnsAlerter(settings)
    assert alerter.configured() is True
    message_id = alerter.publish(
        locality="rohini",
        email="a@b.c",
        subject="test alert",
        body="body",
        message_attributes={"band": "Poor"},
    )
    assert message_id
    client.delete_topic(TopicArn=topic)


def test_evaluate_subscriptions_matches_locality_key() -> None:
    subs = [
        {
            "pk": "sub#1",
            "email": "a@b.c",
            "locality": "rohini",
            "threshold_category": "Poor",
            "last_band": None,
            "last_alerted_at": None,
        }
    ]
    results = evaluate_subscriptions(
        subs, estimates_by_locality={"rohini": 200.0}, now=NOW
    )
    assert len(results) == 1
    assert results[0][1].should_send is True


def test_evaluate_subscriptions_no_estimate_skips() -> None:
    subs = [{"pk": "s", "email": "a@b.c", "locality": "x", "threshold_category": "Poor"}]
    assert evaluate_subscriptions(subs, estimates_by_locality={"y": 200.0}, now=NOW) == []


def test_quiet_hours_boundaries() -> None:
    assert in_quiet_hours(time(22, 0))
    assert in_quiet_hours(time(6, 0))
    assert not in_quiet_hours(time(6, 31))
    assert not in_quiet_hours(time(21, 59))


def test_compose_message_contains_uncertainty_and_unsubscribe() -> None:
    subject, body = compose_message(
        locality="Dwarka",
        pm25_mid=210.0,
        pm25_low=181.0,
        pm25_high=239.0,
        category="Severe",
        likely_category="Industrial area",
        unsubscribe_url="https://dhuan.example/unsub?token=zz",
    )
    assert "Dwarka" in subject
    assert "181-239" in body
    assert "Industrial area" in body
    assert "https://dhuan.example/unsub?token=zz" in body


def test_dedupe_key_shape() -> None:
    assert dedupe_message_key("sub#1", "Severe", "2026-10-15") == "sub#1:Severe:2026-10-15"


def test_min_gap_hours_respected() -> None:
    from dhuan.alerts.alerts import decide

    decision = decide(
        current_pm25=300.0,
        threshold_category="Poor",
        last_band="Moderately Polluted",
        last_alerted_at=NOW - timedelta(hours=1),
        now=NOW,
        min_gap_hours=6,
    )
    assert not decision.should_send
    assert decision.reason == "minimum gap not elapsed"

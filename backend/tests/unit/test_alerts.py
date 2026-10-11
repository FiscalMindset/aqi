"""Alert-rule unit tests: hysteresis, quiet hours, gap, dedupe, message body."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta, timezone

from dhuan.alerts.alerts import (
    AlertDecision,
    compose_message,
    crossed_upward,
    decide,
    dedupe_message_key,
    evaluate_subscriptions,
    in_quiet_hours,
)

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
IST = timezone(timedelta(hours=5, minutes=30))


def _base(**kwargs: object) -> AlertDecision:
    params: dict[str, object] = {
        "current_pm25": 150.0,
        "threshold_category": "Poor",
        "last_band": None,
        "last_alerted_at": None,
        "now": NOW,
    }
    params.update(kwargs)
    return decide(**params)  # type: ignore[arg-type]


def test_crossing_upward_sends() -> None:
    decision = _base()
    assert decision.should_send
    assert decision.band == "Very Poor"


def test_below_threshold_never_sends() -> None:
    decision = _base(current_pm25=40.0)
    assert not decision.should_send
    assert decision.reason == "below threshold"


def test_hysteresis_blocks_second_alert_in_same_band() -> None:
    first = _base()
    assert first.should_send
    second = _base(last_band="Very Poor", last_alerted_at=NOW - timedelta(hours=8))
    assert not second.should_send
    assert "hysteresis" in second.reason


def test_severe_sends_after_poor_alert_when_gap_elapsed() -> None:
    decision = _base(
        current_pm25=300.0, last_band="Poor", last_alerted_at=NOW - timedelta(hours=8)
    )
    assert decision.should_send
    assert decision.band == "Severe"


def test_minimum_gap_blocks_rapid_repeat() -> None:
    decision = _base(
        current_pm25=150.0,
        last_band="Moderately Polluted",
        last_alerted_at=NOW - timedelta(hours=1),
    )
    assert not decision.should_send
    assert decision.reason == "minimum gap not elapsed"


def test_minimum_gap_elapsed_allows() -> None:
    decision = _base(
        current_pm25=150.0,
        last_band="Moderately Polluted",
        last_alerted_at=NOW - timedelta(hours=8),
    )
    assert decision.should_send


def test_quiet_hours_hold_non_severe() -> None:
    night = datetime(2026, 10, 15, 19, 0, tzinfo=UTC)  # 00:30 IST
    decision = _base(now=night)
    assert not decision.should_send
    assert decision.reason == "quiet hours"


def test_severe_breaks_quiet_hours() -> None:
    night = datetime(2026, 10, 15, 19, 0, tzinfo=UTC)
    decision = _base(current_pm25=400.0, now=night)
    assert decision.should_send


def test_quiet_hours_window_crosses_midnight() -> None:
    assert in_quiet_hours(time(23, 0))
    assert in_quiet_hours(time(6, 0))
    assert not in_quiet_hours(time(7, 0))
    assert not in_quiet_hours(time(12, 0))


def test_dedupe_key() -> None:
    key = dedupe_message_key("sub1", "Poor", "2026-10-15")
    assert key == "sub1:Poor:2026-10-15"


def test_dedupe_blocks_repeat() -> None:
    decision = _base(
        current_pm25=300.0,
        last_band="Very Poor",
        last_alerted_at=NOW - timedelta(hours=8),
        dedupe_key="sub1:Severe:2026-10-15",
        recent_keys=["sub1:Severe:2026-10-15"],
    )
    assert not decision.should_send
    assert decision.reason == "duplicate message"


def test_message_states_uncertainty_and_unsubscribe() -> None:
    subject, body = compose_message(
        locality="Rohini",
        pm25_mid=180.0,
        pm25_low=151.0,
        pm25_high=209.0,
        category="Poor",
        likely_category="Landfill",
        unsubscribe_url="https://x.example/unsub?token=abc",
    )
    assert "180" in subject
    assert "151-209" in body
    assert "Landfill" in body
    assert "estimate, not a measurement" in body
    assert "https://x.example/unsub?token=abc" in body


def test_message_hindi_variant() -> None:
    subject, body = compose_message(
        locality="रोहिणी",
        pm25_mid=180.0,
        pm25_low=151.0,
        pm25_high=209.0,
        category="Very Poor",
        likely_category=None,
        unsubscribe_url="https://x.example/unsub",
        language="hi",
    )
    assert "रोहिणी" in subject
    assert "unsubscribe" in body.lower()


def test_evaluate_subscriptions_end_to_end() -> None:
    subs = [
        {
            "pk": "sub#1",
            "email": "a@example.com",
            "locality": "rohini",
            "threshold_category": "Poor",
            "last_band": None,
            "last_alerted_at": None,
        },
        {
            "pk": "sub#2",
            "email": "b@example.com",
            "locality": "dwarka",
            "threshold_category": "Very Poor",
            "last_band": None,
            "last_alerted_at": None,
        },
    ]
    results = evaluate_subscriptions(
        subs,
        estimates_by_locality={"rohini": 110.0, "dwarka": 110.0},
        now=NOW,
    )
    sends = [r for r in results if r[1].should_send]
    assert len(sends) == 1  # sub1 crosses Poor; sub2 needs Very Poor


def test_crossed_upward_helper() -> None:
    assert crossed_upward("Severe", "Poor", "Very Poor")
    assert not crossed_upward("Poor", "Poor", "Poor")
    assert not crossed_upward("Good", "Poor", "Poor")


def test_no_station_reading_means_no_estimate_notified() -> None:
    results = evaluate_subscriptions(
        [{"pk": "sub#1", "email": "a@b.c", "locality": "x",
          "threshold_category": "Poor"}],
        estimates_by_locality={"never-seen-locality": 150.0},
        now=NOW,
    )
    assert results == []

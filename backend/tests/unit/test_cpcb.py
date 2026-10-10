"""Tests for the CPCB category table (pinned against the official document)."""

from __future__ import annotations

import pytest

from dhuan.model.cpcb import (
    CATEGORIES,
    CPCB_TABLE_VERSION,
    aqi_for_pm25,
    band_rank,
    category_for_pm25,
    is_worse,
)


@pytest.mark.parametrize(
    ("pm25", "category"),
    [
        (0.0, "Good"),
        (29.9, "Good"),
        (30.0, "Good"),  # CPCB bands are inclusive at the top end
        (30.1, "Satisfactory"),
        (59.9, "Satisfactory"),
        (60.0, "Satisfactory"),
        (60.1, "Moderately Polluted"),
        (90.0, "Moderately Polluted"),
        (90.1, "Poor"),
        (120.0, "Poor"),
        (120.1, "Very Poor"),
        (249.9, "Very Poor"),
        (250.0, "Very Poor"),
        (250.1, "Severe"),
        (1000.0, "Severe"),
    ],
)
def test_category_breakpoints_match_official_table(pm25: float, category: str) -> None:
    assert category_for_pm25(pm25) == category


def test_documented_interpolation_examples() -> None:
    # From the CPCB document itself: 31 -> 51, 60 -> 100, 45 -> 75.
    assert aqi_for_pm25(31.0) == 51
    assert aqi_for_pm25(60.0) == 100
    assert aqi_for_pm25(45.0) == 75


def test_zero_and_edges() -> None:
    assert aqi_for_pm25(0.0) == 0
    assert aqi_for_pm25(30.0) == 50
    assert aqi_for_pm25(60.0) == 100
    assert aqi_for_pm25(90.0) == 200
    assert aqi_for_pm25(120.0) == 300
    assert aqi_for_pm25(250.0) == 400


def test_severe_clamped_at_500() -> None:
    assert aqi_for_pm25(1000.0) == 500


def test_negative_rejected() -> None:
    with pytest.raises(ValueError):
        category_for_pm25(-1.0)
    with pytest.raises(ValueError):
        aqi_for_pm25(-0.1)


def test_band_ordering_worst_first() -> None:
    assert CATEGORIES[0] == "Severe"
    assert CATEGORIES[-1] == "Good"
    assert band_rank("Severe") == 0
    assert band_rank("Good") == 5


def test_is_worse() -> None:
    assert is_worse("Severe", "Good")
    assert not is_worse("Good", "Severe")
    assert not is_worse("Poor", "Poor")


def test_table_version_recorded() -> None:
    assert CPCB_TABLE_VERSION  # versioned table, not memory

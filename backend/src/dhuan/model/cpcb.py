"""CPCB (Central Pollution Control Board, India) National AQI categories.

VERIFIED against the official CPCB document on 2026-10-15:
  https://cpcb.nic.in/displaypdf.php?id=bmF0aW9uYWwtYWlyLXF1YWxpdHktaW5kZXgvQWJvdXRfQVFJLnBkZg%3D%3D
  (decodes to national-air-quality-index/About_AQI.pdf; verified by downloading
  and extracting the breakpoint table with pypdf).

CPCB breakpoints are **24-hourly averages**. Dhuan estimates hourly values, so
applying the same concentration breakpoints to an hourly value is
*conservative in communication* (an hour reading "Severe" does not imply the
24-hour average is Severe). Every API response that exposes a category derived
from an hourly estimate says so explicitly; the UI repeats it.
"""

from __future__ import annotations

from dataclasses import dataclass

# Version this table whenever CPCB revises it; keep the old rows for old data.
CPCB_TABLE_VERSION = "2014-11-24h-breaks"


@dataclass(frozen=True, slots=True)
class Breakpoint:
    category: str
    aqi_low: int
    aqi_high: int
    pm25_low: float
    pm25_high: float | None  # None = open-ended


# PM2.5, 24-hourly, µg/m³. The Severe high is open-ended (250+).
PM25_BREAKPOINTS: tuple[Breakpoint, ...] = (
    Breakpoint("Good", 0, 50, 0.0, 30.0),
    Breakpoint("Satisfactory", 51, 100, 30.0, 60.0),
    Breakpoint("Moderately Polluted", 101, 200, 60.0, 90.0),
    Breakpoint("Poor", 201, 300, 90.0, 120.0),
    Breakpoint("Very Poor", 301, 400, 120.0, 250.0),
    Breakpoint("Severe", 401, 500, 250.0, None),
)

# Continuous interpolation bands: (c_low, c_high, aqi_low, aqi_high). Band
# endpoints are shared with the published AQI values, reproducing the CPCB
# document's own worked examples exactly (31->51, 45->75, 60->100).
INTERPOLATION_BANDS: tuple[tuple[float, float | None, int, int], ...] = (
    (0.0, 30.0, 0, 50),
    (30.0, 60.0, 50, 100),
    (60.0, 90.0, 100, 200),
    (90.0, 120.0, 200, 300),
    (120.0, 250.0, 300, 400),
    (250.0, None, 400, 500),
)

# Bands used for alert hysteresis, worst-to-best ordering preserved.
CATEGORIES: tuple[str, ...] = tuple(b.category for b in reversed(PM25_BREAKPOINTS))

CATEGORY_HINDI: dict[str, str] = {
    "Good": "अच्छा",
    "Satisfactory": "संतोषजनक",
    "Moderately Polluted": "मध्यम प्रदूषित",
    "Poor": "खराब",
    "Very Poor": "बहुत खराब",
    "Severe": "गंभीर",
}

# Colorblind-safe palette; always paired with text/icon in the UI (WCAG 2.2).
CATEGORY_COLORS: dict[str, str] = {
    "Good": "#1a9850",
    "Satisfactory": "#91cf60",
    "Moderately Polluted": "#fee08b",
    "Poor": "#fc8d59",
    "Very Poor": "#d73027",
    "Severe": "#7f0000",
}

SEVERE_FLOOR_PM25 = 250.0


def category_for_pm25(pm25: float) -> str:
    """CPCB category name for a PM2.5 concentration (µg/m³)."""
    if pm25 < 0:
        raise ValueError("PM2.5 cannot be negative")
    for bp in PM25_BREAKPOINTS:
        if bp.pm25_high is None or pm25 <= bp.pm25_high:
            return bp.category
    return PM25_BREAKPOINTS[-1].category


def aqi_for_pm25(pm25: float) -> int:
    """CPCB sub-index for a PM2.5 value via piecewise-linear interpolation.

    Formula (official): Ip = [(Ihi - Ilo)/(Bhi - Blo)] * (Cp - Blo) + Ilo.
    Values above the Severe band floor are clamped to 500 as CPCB does.
    """
    if pm25 < 0:
        raise ValueError("PM2.5 cannot be negative")
    # Piecewise-linear on the continuous bands; CPCB's worked examples
    # truncate to the integer sub-index.
    for c_low, c_high, aqi_low, aqi_high in INTERPOLATION_BANDS:
        if c_high is None or pm25 <= c_high:
            if c_high is None:
                return aqi_high  # clamp at 500 for the open-ended Severe band
            span = c_high - c_low
            if span <= 0:
                return aqi_low
            return int((aqi_high - aqi_low) / span * (pm25 - c_low) + aqi_low)
    return 500


def band_rank(category: str) -> int:
    """0 = worst, 5 = best; used for hysteresis comparisons."""
    return CATEGORIES.index(category)


def is_worse(a: str, b: str) -> bool:
    """True when category `a` is more polluted than category `b`."""
    return band_rank(a) < band_rank(b)


__all__ = [
    "CATEGORIES",
    "CATEGORY_COLORS",
    "CATEGORY_HINDI",
    "CPCB_TABLE_VERSION",
    "PM25_BREAKPOINTS",
    "SEVERE_FLOOR_PM25",
    "aqi_for_pm25",
    "band_rank",
    "category_for_pm25",
    "is_worse",
]

"""Tests for the alert email template.

These assert the things that silently break in email HTML and cannot be caught
by rendering alone: that the light-mode overrides carry !important (without it
they lose to inline styles and do nothing), that the breakpoints exist, and that
the dark palette matches the web app.
"""

from __future__ import annotations

import re
from html import escape

import pytest

from dhuan.alerts.email_template import (
    CATEGORY_COLOURS,
    compose_html_email,
    station_link,
)
from dhuan.alerts.email_template import _age_phrase

BASE = {
    "locality": "Rohini",
    "pm25_mid": 205.0,
    "pm25_low": 184.0,
    "pm25_high": 226.0,
    "category": "Very Poor",
    "threshold_category": "Poor",
    "served_by": "model",
    "model_version": "gbt-anchored",
    "persistence_anchor": 226.0,
    "model_adjustment": -21.0,
    "unsubscribe_url": "https://example.test/v1/subscriptions/unsubscribe?token=abc",
    "web_url": "https://example.test",
}


@pytest.fixture
def html() -> str:
    return compose_html_email(
        **BASE,
        station_name="New Delhi-8118",
        station_id=8118,
        station_age_hours=1.0,
        weather={
            "temperature_c": 30.2,
            "humidity_pct": 57,
            "wind_speed_ms": 2.4,
            "wind_direction_deg": 68,
            "precipitation_mm": 0.0,
            "pressure_hpa": 1004,
        },
        causes=["Ghazipur landfill - 11 km upwind"],
        advice="Keep windows shut until morning.",
        features=[
            {
                "name": "station_lag24",
                "value": 226.0,
                "unit": "dimensionless",
                "contribution_ugm3": -13.5,
                "absolute_effect_ugm3": 13.5,
            },
            {
                "name": "wind_gust",
                "value": 6.1,
                "unit": "m/s",
                "contribution_ugm3": 3.4,
                "absolute_effect_ugm3": 3.4,
            },
        ],
        model_accuracy={"mae": 11.12},
    )


class TestTheme:
    def test_dark_palette_matches_the_web_app(self, html: str) -> None:
        # tailwind.config.ts: night.900 / night.800, slate-100, emerald-300
        assert "#0b1020" in html  # page
        assert "#111830" in html  # card
        assert "#18213f" in html  # tile
        assert "#f1f5f9" in html  # text-hi
        assert "#6ee7b7" in html  # emerald-300 accent

    def test_card_has_a_visible_border(self, html: str) -> None:
        assert "border:1px solid #223052" in html

    @pytest.mark.parametrize(
        "hex_code", ["#1a9850", "#91cf60", "#fee08b", "#fc8d59", "#d73027", "#7f0000"]
    )
    def test_uses_the_cpcb_scale_not_tailwind_defaults(self, html: str, hex_code: str) -> None:
        assert hex_code in html

    def test_light_fallback_is_declared(self, html: str) -> None:
        assert "prefers-color-scheme: light" in html
        assert '<meta name="color-scheme" content="light dark">' in html

    def test_light_overrides_all_carry_important(self, html: str) -> None:
        """Inline styles beat stylesheet rules; without !important this is a no-op."""
        block = re.search(
            r"@media \(prefers-color-scheme: light\)\s*\{(.*?)\n\}", html, re.S
        )
        assert block is not None, "no light-mode block found"
        rules = re.findall(r"\.([a-z0-9-]+)\s*\{([^}]*)\}", block.group(1))
        assert rules, "light block has no rules"
        for name, body in rules:
            for decl in body.split(";"):
                if decl.strip():
                    assert "!important" in decl, f"light rule .{name} lacks !important: {decl}"

    def test_every_light_class_is_used_in_the_body(self, html: str) -> None:
        """A rule for a class nothing uses is dead CSS; a class in the body with
        no rule means that surface stays dark in light mode."""
        block = re.search(
            r"@media \(prefers-color-scheme: light\)\s*\{(.*?)\n\}", html, re.S
        )
        assert block is not None
        defined = {n for n, _ in re.findall(r"\.([a-z0-9-]+)\s*\{([^}]*)\}", block.group(1))}
        used = set(re.findall(r'class="([^"]+)"', html))
        flat: set[str] = set()
        for group in used:
            flat.update(group.split())
        missing = defined - flat
        assert not missing, f"light-theme rules with no element: {sorted(missing)}"


class TestResponsive:
    @pytest.mark.parametrize("width", ["600px", "480px", "380px"])
    def test_has_a_breakpoint_at_each_width(self, html: str, width: str) -> None:
        assert f"max-width:{width}" in html

    def test_small_screens_shrink_the_page_gutter(self, html: str) -> None:
        # a 311px card plus 2x12px padding overflowed a 320px screen
        assert re.search(r"@media[^{]*max-width:480px[^}]*\{\s*[^}]*\.page\{[^}]*padding-left", html, re.S)

    def test_keeps_600px_base_with_a_fluid_max(self, html: str) -> None:
        assert 'class="wrap card" width="600"' in html
        assert "max-width:600px" in html


class TestContent:
    def test_names_the_station_and_links_to_the_official_reading(self, html: str) -> None:
        assert "New Delhi-8118" in html
        # the href is HTML-escaped (& -> &amp;), which is correct for an attribute
        assert escape(station_link(8118), quote=True) in html
        assert "View the official reading" in html

    def test_shows_the_arithmetic(self, html: str) -> None:
        assert "226.00" not in html  # fixed: unit-aware formatting
        assert "226 µg/m³" in html
        assert "-21.0 µg/m³" in html
        assert "205 µg/m³" in html

    def test_shows_the_parameters_that_moved_it(self, html: str) -> None:
        assert "Nearest station, 24 h ago" in html
        assert "Wind gusts" in html
        assert "What moved this number" in html

    def test_shows_the_conditions(self, html: str) -> None:
        assert "Temperature" in html
        assert "Humidity" in html
        assert "Wind" in html
        assert "ENE (68°)" in html

    def test_non_technical_ordering(self, html: str) -> None:
        """Number first, then what to do, then contributors; the workings last."""
        number = html.index("Estimated PM2.5")
        advice = html.index("What to do")
        causes = html.index("Likely contributors")
        workings = html.index("How this number was worked out")
        assert number < advice < causes < workings

    def test_working_out_is_collapsible(self, html: str) -> None:
        assert "<details" in html
        assert "<summary" in html

    def test_unsubscribe_is_a_real_tokenised_link(self, html: str) -> None:
        assert "/v1/subscriptions/unsubscribe?token=abc" in html

    def test_credits_the_github_account(self, html: str) -> None:
        assert "github.com/FiscalMindset" in html
        assert "@FiscalMindset" in html

    def test_keeps_the_honesty_disclaimer(self, html: str) -> None:
        assert "Estimate, not a measurement" in html
        assert "authoritative source" in html

    def test_declares_both_colour_schemes_for_apple_mail(self, html: str) -> None:
        assert 'name="supported-color-schemes"' in html


class TestMailClientSafety:
    def test_layout_is_table_based(self, html: str) -> None:
        assert "<table" in html
        assert "display:flex" not in html
        assert "display:grid" not in html

    def test_layout_tables_are_hidden_from_screen_readers(self, html: str) -> None:
        tables = re.findall(r"<table[^>]*>", html)
        assert tables
        assert all('role="presentation"' in t for t in tables), "layout table missing role"

    def test_coloured_cells_carry_bgcolor_for_outlook(self, html: str) -> None:
        # Outlook (Windows) honours bgcolor attributes and ignores <style>
        assert html.count("bgcolor=") >= 8

    def test_hides_the_preheader_from_the_visible_body(self, html: str) -> None:
        assert "display:none;max-height:0" in html

    def test_escapes_untrusted_text(self) -> None:
        html = compose_html_email(**{**BASE, "locality": "<script>alert(1)</script>"})
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html


class TestAgeFormatting:
    @pytest.mark.parametrize(
        ("hours", "expected"),
        [
            (0.5, "less than an hour ago"),
            (1.0, "1 h ago"),
            (24.0, "24 h ago"),
            (72.0, "3 days ago"),
            (24.0 * 40, "40 days ago"),
            (24.0 * 90, "3 months ago"),
            (24.0 * 365 * 3, "over 3 years ago"),
        ],
    )
    def test_readable(self, hours: float, expected: str) -> None:
        assert _age_phrase(hours) == expected

    def test_none_is_empty(self) -> None:
        assert _age_phrase(None) == ""


def test_catalogue_colours_cover_every_cpcb_band() -> None:
    assert set(CATEGORY_COLOURS) == {
        "Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"
    }
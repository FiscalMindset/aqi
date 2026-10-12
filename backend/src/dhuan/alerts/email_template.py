"""Responsive HTML alert email.

Email clients are not browsers. The constraints that shaped this file:

* No flexbox, no grid, no CSS variables, no external stylesheets, no web fonts.
  Everything is nested ``<table role="presentation">`` with inline styles.
* Inline styles beat stylesheet rules in the cascade, so the light-mode
  overrides in ``LIGHT_THEME_CSS`` must all carry ``!important``. Without it the
  fallback silently does nothing.
* Outlook (Windows) ignores ``<style>`` entirely and honours ``bgcolor``
  attributes, so every coloured cell also sets ``bgcolor`` as a fallback.
* Outlook does not support ``<details>``; the collapsed section degrades to
  fully expanded content, which is acceptable.

The design matches the web app: the dark ``night`` palette and the CPCB colour
scale from ``frontend/tailwind.config.ts``. Email has no alpha channel, so
``border-white/10`` becomes the opaque ``#223052``.
"""

from __future__ import annotations

from html import escape
from typing import Any

# --------------------------------------------------------------------------
# Palette - mirrors frontend/tailwind.config.ts
# --------------------------------------------------------------------------
CATEGORY_COLOURS: dict[str, str] = {
    # CPCB scale, used as pill backgrounds with white text, so it is identical
    # in both themes.
    "Good": "#1a9850",
    "Satisfactory": "#91cf60",
    "Moderate": "#fee08b",
    "Poor": "#fc8d59",
    "Very Poor": "#d73027",
    "Severe": "#7f0000",
}
CATEGORY_TEXT_ON_PILL: dict[str, str] = {
    # dark text on the two light CPCB bands for contrast
    "Moderate": "#422006",
    "Satisfactory": "#1a2e05",
}

PAGE_BG = "#0b1020"        # night-900
CARD_BG = "#111830"        # night-800
TILE_BG = "#18213f"        # night-700
CARD_BORDER = "#223052"    # opaque form of white/10 on night-800
TEXT_HI = "#f1f5f9"        # slate-100
TEXT_BODY = "#cbd5e1"      # slate-300
TEXT_MUTED = "#94a3b8"     # slate-400
ACCENT = "#6ee7b7"         # emerald-300
UP = "#fcd34d"             # amber-300
DOWN = "#7dd3fc"           # sky-300
TEAL = "#0f766e"           # teal-700

# CPCB scale, in order, for the meter track.
SCALE = ("#1a9850", "#91cf60", "#fee08b", "#fc8d59", "#d73027", "#7f0000")
SCALE_MAX = 400.0

MODEL_DESCRIPTION = (
    "Gradient-boosted decision trees (scikit-learn HistGradientBoostingRegressor, "
    "quantile loss), trained on 591,372 real hourly readings from 73 Delhi-NCR "
    "monitoring stations. It predicts the correction to the nearest station's last "
    "hour, then adds it back."
)

PARAM_LABELS: dict[str, tuple[str, str]] = {
    "station_lag24": ("Nearest station, 24 h ago", "µg/m³"),
    "station_rolling6": ("Nearest station, 6 h average", "µg/m³"),
    "hour_sin": ("Time of day", "—"),
    "hour_cos": ("Time of day (2nd harmonic)", "—"),
    "month_sin": ("Season", "—"),
    "month_cos": ("Season (2nd harmonic)", "—"),
    "wind_speed": ("Wind speed", "m/s"),
    "wind_gust": ("Wind gusts", "m/s"),
    "wind_dir_sin": ("Wind direction", "—"),
    "wind_dir_cos": ("Wind direction (2nd harmonic)", "—"),
    "temp_c": ("Temperature", "°C"),
    "rh": ("Humidity", "%"),
    "precip": ("Rainfall", "mm"),
    "landfill_dist_km": ("Distance to nearest landfill", "km"),
    "landfill_count_5km": ("Landfills within 5 km", "count"),
    "industrial_dist_km": ("Distance to nearest industry", "km"),
    "industrial_count_5km": ("Industries within 5 km", "count"),
    "construction_dist_km": ("Distance to construction", "km"),
    "construction_count_5km": ("Construction within 5 km", "count"),
    "junction_dist_km": ("Distance to nearest junction", "km"),
    "junction_count_5km": ("Junctions within 5 km", "count"),
}

FONT_STACK = (
    "Inter,system-ui,-apple-system,'Segoe UI',Roboto,"
    "'Noto Sans Devanagari','Helvetica Neue',Arial,sans-serif"
)

# Light-mode overrides. Every rule needs !important to beat the inline styles.
LIGHT_THEME_CSS = """
@media (prefers-color-scheme: light) {
  .page{background:#eef2f7 !important;}
  .card{background:#ffffff !important;border-color:#e2e8f0 !important;}
  .tile{background:#f8fafc !important;border-color:#e2e8f0 !important;}
  .rule{border-color:#e2e8f0 !important;}
  .t-h1{color:#0f172a !important;}
  .t-body{color:#334155 !important;}
  .t-muted{color:#64748b !important;}
  .t-accent{color:#047857 !important;}
  .bar-up{background:#b45309 !important;}
  .bar-down{background:#0369a1 !important;}
  .btn{background:#ffffff !important;border-color:#cbd5e1 !important;color:#475569 !important;}
  .btn-primary{background:#059669 !important;color:#ffffff !important;}
  .advice{background:#ecfdf5 !important;border-left-color:#1a9850 !important;}
  .t-advice{color:#14532d !important;}
  .track{background:#e2e8f0 !important;}
  .track-dark{background:#e2e8f0 !important;}
  .chip{background:#f8fafc !important;border-color:#e2e8f0 !important;}
  .panel{background:#f8fafc !important;border-color:#e2e8f0 !important;}
}
"""

RESPONSIVE_CSS = """
@media only screen and (max-width:600px){
  .wrap{width:100% !important;max-width:100% !important;border-radius:12px !important;}
  .pad{padding-left:18px !important;padding-right:18px !important;}
  .h1{font-size:34px !important;}
  .tile-2{width:100% !important;display:block !important;}
  .tile-gap{height:8px !important;}
}
@media only screen and (max-width:480px){
  /* the outer gutter must shrink with the viewport or a 600px card overflows
     a 320px screen: 311px card + 2x12px padding = 335px */
  .page{padding-left:8px !important;padding-right:8px !important;}
  .h1{font-size:30px !important;}
  .brand-sub{display:none !important;}
  .btn{display:block !important;text-align:center !important;}
}
@media only screen and (max-width:380px){
  .page{padding-left:5px !important;padding-right:5px !important;}
  .pad{padding-left:14px !important;padding-right:14px !important;}
  .h1{font-size:27px !important;}
  .kicker{font-size:9px !important;letter-spacing:.06em !important;}
  .brand-sub{display:none !important;}
}
"""

HEAD_STYLE = f"""{RESPONSIVE_CSS}{LIGHT_THEME_CSS}
body{{margin:0;padding:0;background:{PAGE_BG};}}
img{{border:0;outline:none;text-decoration:none;}}
a{{color:{ACCENT};}}
@media (prefers-reduced-motion:no-preference){{ .btn{{transition:opacity .15s ease;}} }}
"""


# --------------------------------------------------------------------------
# small builders
# --------------------------------------------------------------------------
def _kicker(text: str) -> str:
    return (
        f'<p class="kicker t-muted" style="margin:0 0 8px;font-size:10px;font-weight:700;'
        f'letter-spacing:.09em;text-transform:uppercase;color:{TEXT_MUTED};">{escape(text)}</p>'
    )


def _kv(label: str, value: str, *, hi: bool = False, mono: bool = True) -> str:
    colour = TEXT_HI if hi else TEXT_BODY
    family = f"font-family:ui-monospace,Menlo,Consolas,{FONT_STACK};" if mono else ""
    return (
        "<tr>"
        f'<td class="t-body" style="padding:6px 0;color:{colour};font-size:13px;'
        f'line-height:18px;">{escape(label)}</td>'
        f'<td class="t-h1" style="padding:6px 0;text-align:right;color:{TEXT_HI};'
        f'font-size:13px;font-weight:{"700" if hi else "500"};line-height:18px;{family}">'
        f"{escape(value)}</td>"
        "</tr>"
    )


def _stat(label: str, value: str) -> str:
    """One tile in the conditions grid."""
    return (
        f'<td class="tile-2" width="145" valign="top" '
        'style="width:145px;padding:0 4px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:separate;"><tr>'
        f'<td class="tile" bgcolor="{TILE_BG}" '
        'style="background:#18213f;border:1px solid #223052;border-radius:10px;'
        'padding:11px 12px;">'
        f'<p class="t-muted" style="margin:0 0 3px;font-size:10px;letter-spacing:.05em;'
        f'text-transform:uppercase;color:{TEXT_MUTED};">{escape(label)}</p>'
        f'<p class="t-h1" style="margin:0;font-size:15px;font-weight:700;color:{TEXT_HI};'
        f'line-height:20px;">{escape(value)}</p>'
        "</td></tr></table></td>"
    )


def _rule(pad_top: int = 14, pad_bottom: int = 14) -> str:
    return (
        f'<tr><td class="rule pad" style="padding:{pad_top}px 24px {pad_bottom}px;'
        f'border-top:1px solid {CARD_BORDER};font-size:0;line-height:0;">&nbsp;</td></tr>'
    )


def _scale_meter(value: float) -> str:
    """A CPCB-coloured track with a marker at the current value."""
    pct = max(0.0, min(100.0, (value / SCALE_MAX) * 100.0))
    cells = "".join(
        f'<td width="16.6%" bgcolor="{c}" height="8" '
        f'style="height:8px;font-size:0;line-height:0;background:{c};"></td>'
        for c in SCALE
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;margin:14px 0 0;">'
        f'<tr>{cells}</tr></table>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;margin:-6px 0 0;">'
        f'<tr><td width="{pct:.1f}%" style="font-size:0;line-height:0;">&nbsp;</td>'
        '<td align="left" style="font-size:0;line-height:0;">'
        f'<span style="display:inline-block;width:3px;height:16px;background:{TEXT_HI};'
        'border-radius:2px;"></span></td></tr></table>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;margin:2px 0 0;">'
        '<tr>'
        f'<td class="t-muted" style="font-size:9px;color:{TEXT_MUTED};">0</td>'
        f'<td class="t-muted" align="center" style="font-size:9px;color:{TEXT_MUTED};">'
        "CPCB bands &middot; 0&ndash;400 µg/m³</td>"
        f'<td class="t-muted" align="right" style="font-size:9px;color:{TEXT_MUTED};">400</td>'
        "</tr></table>"
    )


def _contribution_bar(
    name: str,
    value: float,
    contribution: float,
    unit: str,
    pct: float,
) -> str:
    """One parameter row: name, signed effect, observed value, proportional bar.

    `pct` is the bar width relative to the largest effect in this email, so the
    reader can see which inputs dominated. The bar colour is amber when the
    parameter pushes the estimate up and sky when it pulls it down, matching the
    app's FeatureBreakdown.
    """
    label, mapped_unit = PARAM_LABELS.get(name, (name.replace("_", " "), unit))
    # The API reports "dimensionless" for features it does not name, which made
    # station readings render as "226.00". Prefer our own label's unit.
    effective = mapped_unit if unit == "dimensionless" else unit
    shown = f"{value:.0f}" if effective in {"µg/m³", "count"} else f"{value:.2f}"
    up = contribution >= 0
    colour = UP if up else DOWN
    bar_class = "bar-up" if up else "bar-down"
    return (
        "<tr><td style=\"padding:5px 0;\">"
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;"><tr>'
        f'<td class="t-body" style="font-size:12px;line-height:16px;color:{TEXT_BODY};">'
        f"{escape(label)}</td>"
        f'<td align="right" class="t-h1" style="font-size:12px;font-weight:700;'
        f'line-height:16px;color:{TEXT_HI};white-space:nowrap;">'
        f'{contribution:+.1f}</td>'
        f'<td align="right" class="t-muted" style="font-size:10px;width:58px;'
        f'color:{TEXT_MUTED};white-space:nowrap;">{escape(shown)}</td>'
        "</tr>"
        '<tr><td colspan="3" style="padding:4px 0 0;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;"><tr>'
        f'<td class="track track-dark" bgcolor="#1b2545" width="100%" '
        'style="height:4px;font-size:0;line-height:0;background:#1b2545;'
        'border-radius:2px;">&nbsp;</td></tr></table>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;margin-top:-4px;"><tr>'
        f'<td width="{pct:.1f}%" class="{bar_class}" bgcolor="{colour}" '
        f'style="height:4px;font-size:0;line-height:0;background:{colour};'
        'border-radius:2px;">&nbsp;</td>'
        '<td style="font-size:0;line-height:0;">&nbsp;</td></tr></table>'
        "</td></tr></table></td></tr>"
    )


def station_link(station_id: int | None, country: str = "IN") -> str:
    """Deep link to the official CPCB dashboard for this station."""
    if station_id is None:
        return ""
    return (
        "https://cpcb.nic.in/RealTime/AQI_Dashboard_Station-wise.aspx"
        f"?CityID=&StateID=&CountryID={country}&StationID={station_id}"
    )


def _age_phrase(hours: float | None) -> str:
    """Readable data age. 24175 h means nothing; 'over 2 years ago' does."""
    if hours is None:
        return ""
    if hours < 1:
        return "less than an hour ago"
    if hours < 48:
        return f"{hours:.0f} h ago"
    days = hours / 24.0
    if days < 60:
        return f"{days:.0f} days ago"
    months = days / 30.44
    if months < 24:
        return f"{months:.0f} months ago"
    return f"over {months / 12:.0f} years ago"


def _compass(deg: float) -> str:
    """Meteorological direction (the direction wind comes FROM)."""
    points = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    ]
    return f"{points[int((deg % 360) / 22.5 + 0.5) % 16]} ({deg:.0f}°)"


# --------------------------------------------------------------------------
# the template
# --------------------------------------------------------------------------
def compose_html_email(
    *,
    locality: str,
    pm25_mid: float,
    pm25_low: float,
    pm25_high: float,
    category: str,
    threshold_category: str,
    served_by: str,
    model_version: str,
    persistence_anchor: float | None,
    model_adjustment: float | None,
    features: list[dict[str, Any]] | None = None,
    station_name: str | None = None,
    station_id: int | None = None,
    station_age_hours: float | None = None,
    weather: dict[str, Any] | None = None,
    causes: list[str] | None = None,
    advice: str | None = None,
    unsubscribe_url: str,
    web_url: str = "",
    model_accuracy: dict[str, float] | None = None,
) -> str:
    colour = CATEGORY_COLOURS.get(category, CATEGORY_COLOURS["Poor"])
    pill_text = CATEGORY_TEXT_ON_PILL.get(category, "#ffffff")
    model_label = (
        "Gradient-boosted trees" if served_by == "model" else "Nearest-station baseline"
    )

    # ---- brand bar ---------------------------------------------------------
    brand = f"""
    <tr><td bgcolor="{CARD_BG}" class="card" style="background:{CARD_BG};padding:16px 24px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;"><tr>
        <td align="left" class="t-h1" style="font-size:15px;font-weight:800;
            letter-spacing:-.01em;color:{TEXT_HI};">Dhuan&nbsp;Detective</td>
        <td class="brand-sub t-muted" align="right" style="font-size:11px;color:{TEXT_MUTED};">
          Delhi-NCR air, explained</td>
      </tr></table>
    </td></tr>"""

    # ---- hero --------------------------------------------------------------
    hero = f"""
    <tr><td align="center" class="pad" style="padding:22px 24px 20px;">
      {_kicker(f"Estimated PM2.5 · {locality}")}
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;"><tr><td align="center">
        <span class="h1 t-h1" style="font-size:40px;font-weight:800;
              letter-spacing:-.02em;color:{TEXT_HI};line-height:44px;">{pm25_mid:.0f}</span>
        <span class="t-muted" style="font-size:15px;color:{TEXT_MUTED};">&nbsp;µg/m³</span>
        <span style="display:inline-block;margin-left:8px;padding:4px 11px;
              border-radius:999px;background:{colour};color:{pill_text};
              font-size:11px;font-weight:800;letter-spacing:.02em;">{escape(category)}</span>
      </td></tr></table>
      <p class="t-muted" style="margin:8px 0 0;font-size:12px;color:{TEXT_MUTED};">
        80% range {pm25_low:.0f}&ndash;{pm25_high:.0f} µg/m³
      </p>
      {_scale_meter(pm25_mid)}
      <p class="t-muted" style="margin:10px 0 0;font-size:12px;line-height:17px;
         color:{TEXT_MUTED};">
        Air crossed <strong class="t-body">{escape(threshold_category)}</strong>
        here. This is our estimate, not a measurement.
      </p>
    </td></tr>"""

    # ---- station provenance -------------------------------------------------
    provenance = ""
    if station_name:
        href = station_link(station_id)
        cta = (
            f'<a href="{escape(href)}" class="btn chip" style="display:inline-block;'
            f'padding:7px 13px;background:{TILE_BG};border:1px solid {CARD_BORDER};'
            f'border-radius:8px;color:{ACCENT};font-size:12px;font-weight:700;'
            f'text-decoration:none;">View the official reading &rarr;</a>'
            if href
            else ""
        )
        when = ""
        phrase = _age_phrase(station_age_hours)
        if phrase:
            when = f" &middot; reading {phrase}"
        provenance = f"""
    <tr><td class="pad" style="padding:0 24px 16px;">
      <table role="presentation" class="tile" width="100%" cellpadding="0" cellspacing="0"
             bgcolor="{TILE_BG}"
             style="background:{TILE_BG};border:1px solid {CARD_BORDER};
                    border-radius:12px;"><tr>
        <td style="padding:13px 15px;">
          {_kicker("Where this comes from")}
          <p class="t-body" style="margin:0 0 10px;font-size:13px;line-height:19px;
             color:{TEXT_BODY};">Official monitoring station
             <strong class="t-h1" style="color:{TEXT_HI};">{escape(station_name)}</strong>{when}
          </p>
          {cta}
        </td></tr></table>
    </td></tr>"""

    # ---- advice ------------------------------------------------------------
    advice_block = ""
    if advice:
        advice_block = f"""
    <tr><td class="pad" style="padding:0 24px 16px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:separate;"><tr>
        <td class="advice" bgcolor="#0c2b26"
            style="background:#0c2b26;border-left:3px solid #6ee7b7;border-radius:8px;
                   padding:13px 15px;">
          <p class="kicker t-accent" style="margin:0 0 5px;font-size:10px;font-weight:700;
             letter-spacing:.09em;text-transform:uppercase;color:{ACCENT};">What to do</p>
          <p class="t-advice" style="margin:0;font-size:13px;line-height:20px;color:#d1fae5;">
            {escape(advice)}</p>
        </td></tr></table>
    </td></tr>"""

    # ---- contributors ------------------------------------------------------
    contributors = ""
    if causes:
        chips = "".join(
            f'<span class="chip t-body" style="display:inline-block;margin:0 6px 6px 0;'
            f'padding:5px 10px;background:{TILE_BG};border:1px solid {CARD_BORDER};'
            f'border-radius:999px;font-size:11px;color:{TEXT_BODY};">{escape(c)}</span>'
            for c in causes[:3]
        )
        contributors = f"""
    <tr><td class="pad" style="padding:0 24px 18px;">
      {_kicker("Likely contributors")}
      <div style="font-size:0;line-height:0;">{chips}</div>
    </td></tr>"""

    # ---- conditions --------------------------------------------------------
    conditions = ""
    if weather:
        w = weather
        tiles = []
        if w.get("temperature_c") is not None:
            tiles.append(_stat("Temperature", f"{w['temperature_c']:.0f}°C"))
        if w.get("humidity_pct") is not None:
            tiles.append(_stat("Humidity", f"{w['humidity_pct']:.0f}%"))
        if w.get("wind_speed_ms") is not None:
            tiles.append(_stat("Wind", f"{w['wind_speed_ms']:.1f} m/s"))
        if w.get("wind_direction_deg") is not None:
            tiles.append(_stat("Direction", _compass(float(w["wind_direction_deg"]))))
        if w.get("precipitation_mm") is not None:
            tiles.append(_stat("Rainfall", f"{w['precipitation_mm']:.1f} mm"))
        if w.get("pressure_hpa") is not None:
            tiles.append(_stat("Pressure", f"{w['pressure_hpa']:.0f}"))
        if tiles:
            rows = ""
            for i in range(0, len(tiles), 2):
                pair = tiles[i : i + 2]
                while len(pair) < 2:
                    pair.append('<td class="tile-2" width="145" style="width:145px;"></td>')
                rows += f'<tr>{pair[0]}{pair[1]}</tr>'
                if i + 2 < len(tiles):
                    rows += '<tr><td colspan="2" class="tile-gap" style="height:8px;font-size:0;line-height:0;">&nbsp;</td></tr>'
            conditions = f"""
    <tr><td class="pad" style="padding:0 24px 18px;">
      {_kicker("Conditions over this area now")}
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;">{rows}</table>
    </td></tr>"""

    # ---- the workings ------------------------------------------------------
    if persistence_anchor is not None and model_adjustment is not None:
        anchor_label = (
            f"{station_name}, {_age_phrase(station_age_hours)}"
            if station_name
            else f"Nearest station, {_age_phrase(station_age_hours) or '1 h ago'}"
        )
        arithmetic = (
            _kv(anchor_label, f"{persistence_anchor:.0f} µg/m³")
            + _kv(
                "What the model added",
                f"{model_adjustment:+.1f} µg/m³",
                hi=model_adjustment < 0,
            )
            + _kv("Final estimate", f"{pm25_mid:.0f} µg/m³", hi=True)
            + _kv("Algorithm", model_label, mono=False)
            + _kv("Model version", model_version[:22], mono=False)
        )
        if model_accuracy:
            arithmetic += _kv(
                "Typical error (held out)",
                f"±{model_accuracy.get('mae', 0):.0f} µg/m³",
                mono=False,
            )

        bars = ""
        if features:
            used = [
                f for f in features
                if abs(float(f.get("contribution_ugm3", 0))) >= 0.5
            ][:6]
            biggest = max(
                (abs(float(f.get("contribution_ugm3", 0))) for f in used), default=1.0
            ) or 1.0
            for f in used:
                effect = float(f.get("contribution_ugm3", 0))
                bars += _contribution_bar(
                    str(f.get("name")),
                    float(f.get("value", 0)),
                    effect,
                    str(f.get("unit", "")),
                    max(3.0, (abs(effect) / biggest) * 100.0),
                )

        workings = f"""
    <tr><td class="pad" style="padding:0 24px 18px;">
      <details class="panel" style="background:{TILE_BG};border:1px solid {CARD_BORDER};
               border-radius:12px;padding:0;">
        <summary class="t-h1" style="padding:12px 15px;font-size:13px;font-weight:700;
                   color:{TEXT_HI};cursor:pointer;">How this number was worked out</summary>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;border-top:1px solid {CARD_BORDER};">
          <tr><td class="pad" style="padding:13px 15px 4px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="border-collapse:collapse;">{arithmetic}</table>
          </td></tr>
          <tr><td class="pad" style="padding:8px 15px 14px;">
            {_kicker(f"What moved this number ({len(used)} of {len(features)} parameters)"
                     if features else "Parameters")}
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="border-collapse:collapse;">{bars}</table>
            <p class="t-muted" style="margin:8px 0 0;font-size:10px;line-height:15px;
               color:{TEXT_MUTED};">Associations in µg/m³: how far the estimate moves if
               that one parameter were typical. Not causal claims.</p>
          </td></tr>
        </table>
      </details>
    </td></tr>"""
    else:
        workings = ""

    # ---- buttons -----------------------------------------------------------
    primary = (
        f'<a href="{escape(web_url)}" class="btn btn-primary" '
        'style="display:inline-block;padding:12px 24px;background:#059669;color:#ffffff;'
        'text-decoration:none;font-size:14px;font-weight:700;border-radius:9px;">'
        "See the live map</a>"
        if web_url
        else ""
    )

    return f"""<!doctype html>
<html lang="en" xmlns:v="urn:schemas-microsoft-com:vml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<meta name="x-apple-disable-message-reformatting">
<title>Dhuan Detective: {escape(locality)} is {escape(category)}</title>
<style>{HEAD_STYLE}</style>
</head>
<body>
<div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all;">
  {escape(locality)} is {escape(category)}: estimated {pm25_mid:.0f} µg/m³
  (80% range {pm25_low:.0f}&ndash;{pm25_high:.0f}). Details below.
</div>
<table role="presentation" class="page" width="100%" cellpadding="0" cellspacing="0"
       bgcolor="{PAGE_BG}" style="background:{PAGE_BG};padding:20px 12px;">
  <tr><td align="center">
    <table role="presentation" class="wrap card" width="600" cellpadding="0" cellspacing="0"
           bgcolor="{CARD_BG}"
           style="width:600px;max-width:600px;background:{CARD_BG};
                  border:1px solid {CARD_BORDER};border-radius:16px;overflow:hidden;
                  font-family:{FONT_STACK};">
      {brand}
      {hero}
      {_rule(0, 18)}
      {provenance}
      {advice_block}
      {contributors}
      {conditions}
      {_rule(0, 18)}
      {workings}
      <tr><td class="pad" align="center" style="padding:4px 24px 20px;">{primary}</td></tr>
      <tr><td class="pad rule card" bgcolor="#0d1430"
            style="background:#0d1430;border-top:1px solid {CARD_BORDER};padding:16px 24px 20px;">
        <p class="t-muted" style="margin:0 0 12px;font-size:11px;line-height:17px;
           color:{TEXT_MUTED};">
          <strong class="t-body" style="color:{TEXT_BODY};">Estimate, not a measurement.</strong>
          Official CPCB station readings remain the authoritative source. The interval is
          the model's calibrated 80% range; CPCB categories are defined on 24-hour
          averages and applied here to hourly values, which is deliberately conservative.
        </p>
        <p class="t-muted" style="margin:0 0 14px;font-size:11px;line-height:17px;
           color:{TEXT_MUTED};">Model: {escape(MODEL_DESCRIPTION)}</p>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;"><tr>
          <td align="left" style="font-size:0;line-height:0;">
            <a href="{escape(unsubscribe_url)}" class="btn"
               style="display:inline-block;padding:9px 16px;background:{TILE_BG};
                      border:1px solid {CARD_BORDER};border-radius:8px;
                      color:{TEXT_MUTED};text-decoration:none;font-size:12px;
                      font-weight:700;">Unsubscribe</a>
          </td>
          <td class="t-muted" align="right" style="font-size:11px;color:{TEXT_MUTED};
              line-height:17px;">
            <a href="https://github.com/FiscalMindset" class="t-accent"
               style="color:{ACCENT};text-decoration:none;font-weight:700;"
               >@FiscalMindset</a> <span class="t-muted">on GitHub</span><br>
            <a href="https://github.com/FiscalMindset/dhuan" class="t-muted"
               style="color:{TEXT_MUTED};text-decoration:none;"
               >github.com/FiscalMindset/dhuan</a>
          </td>
        </tr></table>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


__all__ = [
    "CATEGORY_COLOURS",
    "CATEGORY_TEXT_ON_PILL",
    "MODEL_DESCRIPTION",
    "PARAM_LABELS",
    "compose_html_email",
    "station_link",
]

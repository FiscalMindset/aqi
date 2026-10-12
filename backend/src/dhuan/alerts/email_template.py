"""Responsive HTML alert email.

Email clients are not browsers: no flexbox, no grid, no external CSS, no web
fonts. Everything here is a table with inline styles and a single media query,
which is what Gmail, Outlook and Apple Mail all render. A `multipart/alternative`
message carries this HTML alongside a plain-text fallback so it degrades
gracefully.

The content answers the questions the reader actually has when an alert lands:
what is the number, how confident are we, which inputs drove it, what the air is
doing right now, and what to do.
"""

from __future__ import annotations

from html import escape
from typing import Any

CATEGORY_COLOURS: dict[str, str] = {
    "Good": "#22c55e",
    "Satisfactory": "#84cc16",
    "Moderate": "#facc15",
    "Poor": "#f97316",
    "Very Poor": "#ef4444",
    "Severe": "#a21caf",
}

MODEL_DESCRIPTION = (
    "Gradient-boosted decision trees (scikit-learn HistGradientBoostingRegressor, "
    "quantile loss), trained on 22,106 real hourly CPCB/OpenAQ readings. It "
    "predicts the correction to the nearest station's last hour, then adds it back."
)

# Human labels + units for the parameters the model actually used.
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


def _fmt(value: float, unit: str) -> str:
    if unit == "—":
        return f"{value:.2f}"
    if unit == "count":
        return f"{value:.0f}"
    if unit == "µg/m³":
        return f"{value:.0f}"
    return f"{value:.1f} {unit}"


def _row(label: str, value: str, colour: str = "#0f172a", bold: bool = False) -> str:
    weight = "600" if bold else "400"
    return (
        "<tr>"
        f'<td style="padding:7px 0;color:#475569;font-size:13px;'
        f'line-height:18px;">{escape(label)}</td>'
        f'<td style="padding:7px 0;text-align:right;color:{colour};font-size:13px;'
        f'font-weight:{weight};line-height:18px;font-family:ui-monospace,Menlo,Consolas,monospace;">'
        f"{escape(value)}</td>"
        "</tr>"
    )


def _section(title: str, rows: str) -> str:
    return (
        '<tr><td style="padding:0 0 8px;">'
        '<p style="margin:0 0 6px;font-size:11px;font-weight:700;letter-spacing:.08em;'
        'text-transform:uppercase;color:#94a3b8;">'
        f"{escape(title)}</p>"
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;">'
        f"{rows}</table></td></tr>"
    )


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
    """Full responsive HTML email. Pure string templating on purpose."""
    colour = CATEGORY_COLOURS.get(category, "#f97316")
    model_label = (
        "Gradient-boosted trees" if served_by == "model" else "Nearest-station baseline"
    )

    # ---- header: the number -------------------------------------------------
    width_pct = max(0, min(100, (pm25_mid / 400.0) * 100))
    header = f"""
    <tr><td align="center" style="padding:4px 0 18px;">
      <p style="margin:0 0 6px;font-size:13px;color:#64748b;">Estimated PM2.5 &middot;
        {escape(locality)}</p>
      <p style="margin:0;text-align:center;">
        <span style="font-size:40px;font-weight:700;color:#0f172a;">{pm25_mid:.0f}</span>
        <span style="font-size:16px;color:#64748b;"> µg/m³</span>
        <span style="display:inline-block;margin-left:8px;padding:3px 10px;border-radius:999px;
          background:{colour}1a;color:{colour};font-size:12px;font-weight:700;
                "">{escape(category)}</span>
      </p>
      <p style="margin:6px 0 0;font-size:12px;color:#64748b;text-align:center;">
        80% range {pm25_low:.0f}&ndash;{pm25_high:.0f} µg/m³
      </p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;margin-top:10px;">
        <tr><td style="background:#e2e8f0;border-radius:999px;height:6px;font-size:0;
              "line-height:0;">&nbsp;</td></tr>
        <tr><td style="height:0;line-height:0;font-size:0;">&nbsp;</td></tr>
      </table>
      <div style="height:6px;border-radius:999px;background:{colour};width:{width_pct:.0f}%;
        margin-top:-6px;"></div>
    </td></tr>"""

    # ---- official source card (verifiability beats marketing) -------------
    href = station_link(station_id)
    station_link_html = ""
    if station_name:
        inner = (
            f'<a href="{escape(href)}" style="color:#0369a1;text-decoration:none;'
            'font-weight:600;">View the official reading &rarr;</a>'
            if href
            else '<span style="color:#64748b;">Official CPCB dashboard</span>'
        )
        station_link_html = (
            '<tr><td style="padding:12px 14px;background:#f8fafc;border:1px solid #e2e8f0;'
            'border-radius:10px;">'
            '<p style="margin:0 0 4px;font-size:11px;font-weight:700;letter-spacing:.06em;'
            'text-transform:uppercase;color:#94a3b8;">Where this comes from</p>'
            f'<p style="margin:0 0 6px;font-size:13px;color:#334155;line-height:19px;">'
            f"Official monitoring station <strong>{escape(station_name)}</strong>"
            + (f" &middot; reading from {station_age_hours:.0f} h ago"
               if station_age_hours is not None and station_age_hours >= 1 else "")
            + "</p>"
            f'<p style="margin:0;font-size:12px;">{inner}</p>'
            "</td></tr>"
        )

    # ---- how the number was produced ---------------------------------------
    if persistence_anchor is not None and model_adjustment is not None:
        # Name the station we anchored on, and link straight to its official
        # reading. "226 ug/m3 from somewhere" is not verifiable; "226 ug/m3 from
        # New Delhi-8118, here is the government page" is.
        if station_age_hours is not None and station_age_hours >= 1:
            when = f"{station_age_hours:.0f} h ago"
        else:
            when = "1 h ago"
        anchor_label = (
            f"{station_name}, {when}" if station_name
            else f"Nearest station, {when}"
        )
        how_rows = _row(anchor_label, f"{persistence_anchor:.0f} µg/m³")
        how_rows += _row(
            "What the model added",
            f"{model_adjustment:+.1f} µg/m³",
            colour="#0369a1" if model_adjustment < 0 else "#b45309",
        )
        how_rows += _row("Final estimate", f"{pm25_mid:.0f} µg/m³", bold=True)
    else:
        how_rows = _row("Basis", "Nearest station's last reading", bold=True)
    how_rows += _row("Algorithm", model_label)
    how_rows += _row("Model version", model_version[:24])
    if model_accuracy:
        how_rows += _row(
            "Typical error (held out)", f"±{model_accuracy.get('mae', 0):.0f} µg/m³"
        )

    # ---- the parameters that actually drove it -----------------------------
    if features:
        used = [f for f in features if abs(float(f.get("contribution_ugm3", 0))) >= 0.5][:6]
        rows = ""
        for f in used:
            label = PARAM_LABELS.get(
                str(f.get("name")), (str(f.get("name", "")).replace("_", " "), "")
            )[0]
            contrib = float(f.get("contribution_ugm3", 0))
            colour_i = "#b45309" if contrib > 0 else "#0369a1"
            rows += _row(label, f"{contrib:+.1f}", colour=colour_i)
        param_section = (
            _section(
                f"What moved this number ({len(used)} of {len(features)} parameters)",
                rows,
            )
            if rows
            else ""
        )
    else:
        param_section = ""

    # ---- current conditions -------------------------------------------------
    if weather:
        w = weather
        rows = ""
        if w.get("temperature_c") is not None:
            rows += _row("Temperature", f"{w['temperature_c']:.1f} °C")
        if w.get("humidity_pct") is not None:
            rows += _row("Humidity", f"{w['humidity_pct']:.0f} %")
        if w.get("wind_speed_ms") is not None:
            rows += _row("Wind speed", f"{w['wind_speed_ms']:.1f} m/s")
        if w.get("wind_direction_deg") is not None:
            rows += _row("Wind direction", _compass(float(w["wind_direction_deg"])))
        if w.get("pressure_hpa") is not None:
            rows += _row("Pressure", f"{w['pressure_hpa']:.0f} hPa")
        if w.get("precipitation_mm") is not None:
            rows += _row("Rainfall", f"{w['precipitation_mm']:.1f} mm")
        if w.get("observed_at"):
            rows += _row("Observed", str(w["observed_at"])[:16].replace("T", " "))
        weather_section = _section("Conditions over this area right now", rows) if rows else ""
    else:
        weather_section = ""

    # ---- likely causes ------------------------------------------------------
    if causes:
        items = "".join(
            f'<li style="margin:0 0 4px;color:#334155;font-size:13px;'
            f'line-height:19px;">{escape(c)}</li>'
            for c in causes[:4]
        )
        causes_section = (
            '<tr><td style="padding:0 0 8px;">'
            '<p style="margin:0 0 6px;font-size:11px;font-weight:700;letter-spacing:.08em;'
            'text-transform:uppercase;color:#94a3b8;">Likely contributors</p>'
            f"<ul style='margin:0;padding-left:18px;'>{items}</ul></td></tr>"
        )
    else:
        causes_section = ""

    advice_block = (
        '<tr><td style="padding:14px 16px;background:#f0fdf4;border-left:3px solid #22c55e;'
        'border-radius:6px;">'
        f'<p style="margin:0;font-size:13px;line-height:20px;color:#14532d;">{escape(advice)}</p>'
        "</td></tr>"
        if advice
        else ""
    )

    button = (
        f'<a href="{escape(web_url)}" style="display:inline-block;padding:11px 22px;'
        'background:#059669;color:#ffffff;text-decoration:none;font-size:14px;font-weight:600;'
        f'border-radius:8px;">See the live map</a>'
        if web_url
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Dhuan Detective alert for {escape(locality)}</title>
<style>
  @media only screen and (max-width:600px) {{
    .wrap {{ width:100% !important; }}
    .pad {{ padding:16px !important; }}
    .h1 {{ font-size:32px !important; }}
    .stack {{ display:block !important; width:100% !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">
  {escape(locality)} is {escape(category)}: estimated {pm25_mid:.0f} µg/m³
  (80% range {pm25_low:.0f}&ndash;{pm25_high:.0f}). Details below.
</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:#f1f5f9;padding:16px 0;">
  <tr><td align="center">
    <table role="presentation" class="wrap" width="600" cellpadding="0" cellspacing="0"
           style="width:600px;max-width:600px;background:#ffffff;border-radius:14px;
                  overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',
                  Roboto,Helvetica,Arial,sans-serif;">
      <tr><td class="pad" style="padding:22px 24px 6px;">
        <p style="margin:0;font-size:15px;font-weight:700;color:#0f172a;">Dhuan Detective</p>
        <p style="margin:2px 0 0;font-size:12px;color:#64748b;">
          Air crossed <strong>{escape(threshold_category)}</strong> in {escape(locality)}
        </p>
      </td></tr>
      <tr><td class="pad" style="padding:8px 24px 16px;">{header}</td></tr>

      <tr><td class="pad" style="padding:0 24px 14px;">{station_link_html}</td></tr>

      <tr><td class="pad" style="padding:0 24px 14px;">{advice_block}</td></tr>

      <tr><td class="pad" style="padding:0 24px 14px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;border-top:1px solid #e2e8f0;">
          {causes_section}
        </table>
      </td></tr>

      <tr><td class="pad" style="padding:0 24px 14px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;border-top:1px solid #e2e8f0;">
          {weather_section}
        </table>
      </td></tr>

      <tr><td class="pad" style="padding:0 24px 14px;">
        <details style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;
          padding:0;">
          <summary style="padding:11px 14px;font-size:13px;font-weight:600;color:#334155;
            cursor:pointer;">How this number was worked out</summary>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="border-collapse:collapse;border-top:1px solid #e2e8f0;">
            {how_rows and _section("The arithmetic", how_rows)}
          </table>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="border-collapse:collapse;">
            {param_section}
          </table>
        </details>
      </td></tr>
      <tr><td class="pad" align="center" style="padding:16px 24px;">
        {button}
      </td></tr>
      <tr><td class="pad" style="padding:14px 24px 22px;">
        <p style="margin:0 0 8px;font-size:11px;line-height:17px;color:#94a3b8;">
          <strong>Estimate, not a measurement.</strong> Official CPCB station
          readings remain the authoritative source. The interval is the model's
          calibrated 80% range; CPCB categories are defined on 24-hour averages
          and applied here to hourly values, which is deliberately conservative.
        </p>
        <p style="margin:0 0 8px;font-size:11px;line-height:17px;color:#94a3b8;">
          Model: {escape(MODEL_DESCRIPTION)}
        </p>
        <p style="margin:0 0 10px;">
          <a href="{escape(unsubscribe_url)}"
             style="display:inline-block;padding:8px 16px;background:#f1f5f9;
                    color:#475569;text-decoration:none;font-size:12px;font-weight:600;
                    border:1px solid #cbd5e1;border-radius:6px;">Unsubscribe</a>
        </p>
        <p style="margin:0;padding-top:10px;border-top:1px solid #e2e8f0;font-size:11px;
          line-height:17px;color:#94a3b8;">
          Built as an open project &middot;
          <a href="https://github.com/FiscalMindset"
             style="color:#059669;text-decoration:none;font-weight:600;">@FiscalMindset on GitHub</a>
          &middot; follow the build at
          <a href="https://github.com/FiscalMindset/dhuan"
             style="color:#059669;text-decoration:none;">github.com/FiscalMindset/dhuan</a>
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


def station_link(station_id: int | None, country: str = "IN") -> str:
    """Deep link to the official CPCB dashboard for this station.

    Lets the reader verify our number against the authoritative source in one
    click, which is the whole point of stating which station we anchored on.
    """
    if station_id is None:
        return ""
    return (
        "https://cpcb.nic.in/RealTime/AQI_Dashboard_Station-wise.aspx"
        f"?CityID=&StateID=&CountryID={country}&StationID={station_id}"
    )


def _compass(deg: float) -> str:
    """Meteorological direction (the direction wind comes FROM)."""
    points = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    ]
    return f"{points[int((deg % 360) / 22.5 + 0.5) % 16]} ({deg:.0f}°)"


__all__ = ["CATEGORY_COLOURS", "MODEL_DESCRIPTION", "PARAM_LABELS", "compose_html_email"]

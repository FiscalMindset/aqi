"""Build the retrieval corpus for one point from what the tools already returned.

This is the bridge between the agent's tool calls and `dhuan.agents.retrieval`.
Every passage here is a fact we can point at: a station reading, a source with a
distance and a bearing, a wind observation, a measured model metric. Nothing is
inferred beyond arithmetic we can show.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from dhuan.agents.retrieval import Passage
from dhuan.model.cpcb import CPCB_TABLE_VERSION, category_for_pm25

CPCB_BAND_TEXT: dict[str, str] = {
    "Good": "0-30 ug/m3, the air is considered to pose little or no risk.",
    "Satisfactory": "31-60 ug/m3, pollution is tolerable for most people.",
    "Moderate": "61-90 ug/m3, sensitive groups may feel effects.",
    "Poor": (
        "91-120 ug/m3, breathing discomfort for everyone, "
        "serious effects for sensitive groups."
    ),
    "Very Poor": "121-250 ug/m3, healthy people are affected and serious effects are widespread.",
    "Severe": "above 250 ug/m3, health effects are severe and irreversible.",
}

TYPE_LABEL: dict[str, str] = {
    "landfill": "landfill",
    "waste_disposal": "waste site",
    "industrial": "industrial site",
    "construction": "construction site",
    "major_junction": "major junction",
    "power_plant": "power plant",
    "other": "emission source",
}


def compass(deg: float | None) -> str:
    if deg is None:
        return "unknown direction"
    points = [
        "north", "north-northeast", "northeast", "east-northeast",
        "east", "east-southeast", "southeast", "south-southeast",
        "south", "south-southwest", "southwest", "west-southwest",
        "west", "west-northwest", "northwest", "north-northwest",
    ]
    return points[int((deg % 360) / 22.5 + 0.5) % 16]


def source_name(raw: dict[str, Any], kind: str) -> str:
    name = str(raw.get("name") or "").strip()
    if name and name.lower() not in {"other", "unknown", kind, TYPE_LABEL.get(kind, "")}:
        return name
    return TYPE_LABEL.get(kind, "emission source")


def build_passages(
    *,
    estimate: Any,
    stations: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    weather: dict[str, Any] | None,
    model_accuracy: dict[str, Any] | None,
    fires: int | None = None,
    evidence_ids: dict[str, str] | None = None,
) -> list[Passage]:
    """Every citable fact about one point, as passages."""
    ids = evidence_ids or {}
    out: list[Passage] = []
    pm25 = float(getattr(estimate, "pm25_mid", 0.0) or 0.0)

    # ---- what is actually measured nearby ---------------------------------
    for i, s in enumerate(stations[:3]):
        value = s.get("pm25")
        if value is None:
            continue
        age = s.get("age_seconds")
        name = str(s.get("name") or "an unnamed station")
        out.append(
            Passage(
                passage_id=f"station-{i}",
                kind="station_reading",
                text=(
                    f"Official monitoring station {name} measured PM2.5 "
                    f"{float(value):.0f} micrograms per cubic metre"
                    + (f", {float(age) / 3600:.0f} hours before the estimate" if age else "")
                    + ". This is a measurement, not a model output."
                ),
                facts={
                    "station": name,
                    "pm25": float(value),
                    "distance_km": s.get("distance_km"),
                    "sensor_id": s.get("sensor_id"),
                },
                authority=0.97,
                measured=True,
                observed_at=s.get("observed_at"),
                age_seconds=age,
                source_url=_openaq_url(name),
                evidence_id=ids.get("station"),
            )
        )

    # ---- trend -------------------------------------------------------------
    trend = _trend_from(stations)
    if trend is not None:
        direction, delta, hours = trend
        out.append(
            Passage(
                passage_id="station-trend",
                kind="station_trend",
                text=(
                    f"PM2.5 at the nearest station is {abs(delta):.0f} micrograms "
                    f"{'higher' if delta > 0 else 'lower'} than {hours} hours ago"
                    f" ({'worsening' if delta > 0 else 'improving'})."
                ),
                facts={"delta": delta, "hours": hours, "direction": direction},
                authority=0.9,
                measured=True,
                evidence_id=ids.get("station"),
            )
        )

    # ---- what we estimate, and with what uncertainty -----------------------
    low = float(getattr(estimate, "pm25_low", 0.0) or 0.0)
    high = float(getattr(estimate, "pm25_high", 0.0) or 0.0)
    served_by = str(getattr(estimate, "served_by", "unknown"))
    anchor = getattr(estimate, "persistence_anchor_ugm3", None)
    adjustment = getattr(estimate, "model_adjustment_ugm3", None)
    cat = category_for_pm25(pm25)
    anchor_txt = ""
    if anchor is not None and adjustment is not None:
        anchor_txt = (
            f" It starts from the nearest station's {float(anchor):.0f} micrograms "
            f"one hour ago and the model corrects that by "
            f"{float(adjustment):+.1f} micrograms."
        )
    elif served_by == "nearest-station":
        anchor_txt = (
            " It is the nearest station's own reading, repeated unchanged, because "
            "the model could not be used for this point."
        )
    out.append(
        Passage(
            passage_id="model-estimate",
            kind="model_estimate",
            text=(
                f"Our estimate here is {pm25:.0f} micrograms per cubic metre, in the "
                f"CPCB {cat} band, with an 80% range of {low:.0f} to {high:.0f}."
                + anchor_txt
            ),
            facts={
                "pm25": pm25,
                "low": low,
                "high": high,
                "category": cat,
                "served_by": served_by,
                "anchor": anchor,
                "adjustment": adjustment,
            },
            authority=0.86,
            source_url=None,
        )
    )

    out.append(
        Passage(
            passage_id="cpcb-band",
            kind="cpcb_band",
            text=(
                f"The CPCB {cat} band ({CPCB_TABLE_VERSION}) means: "
                f"{CPCB_BAND_TEXT.get(cat, '')}"
            ),
            facts={"category": cat, "table_version": CPCB_TABLE_VERSION},
            authority=0.95,
        )
    )

    # ---- what moved the number --------------------------------------------
    feats = list(getattr(estimate, "features_used", []) or [])
    strong = sorted(
        feats,
        key=lambda f: -abs(float(getattr(f, "contribution_ugm3", 0) or 0)),
    )[:3]
    for i, f in enumerate(strong):
        name = str(getattr(f, "name", ""))
        effect = float(getattr(f, "contribution_ugm3", 0) or 0)
        if abs(effect) < 0.5:
            continue
        out.append(
            Passage(
                passage_id=f"param-{i}",
                kind="model_parameters",
                text=(
                    f"The parameter {name.replace('_', ' ')} moved this estimate by "
                    f"{effect:+.1f} micrograms relative to a typical value for Delhi."
                ),
                facts={"name": name, "contribution": effect},
                authority=0.8,
            )
        )

    # ---- how much to trust it ---------------------------------------------
    if model_accuracy:
        mae = float(model_accuracy.get("mae") or 0.0)
        unseen = float(model_accuracy.get("unseen_mae") or 0.0)
        txt = f"On held-out future hours this model is wrong by {mae:.1f} micrograms on average."
        if unseen:
            txt += (
                f" At a monitoring station it has never seen it is wrong by "
                f"{unseen:.1f} micrograms, which is the honest limit of the method."
            )
        out.append(
            Passage(
                passage_id="model-accuracy",
                kind="model_accuracy",
                text=txt,
                facts={"mae": mae, "unseen_mae": unseen or None},
                authority=0.95,
            )
        )

    # ---- sources -----------------------------------------------------------
    for i, s in enumerate(sources[:4]):
        kind = str(s.get("type") or "other")
        dist = s.get("distance_km")
        bearing = s.get("bearing_deg")
        upwind = bool(s.get("in_upwind_cone"))
        influence = float(s.get("influence_score") or 0.0)
        name = source_name(s, kind)
        where = ""
        if dist is not None:
            where = f" {float(dist):.1f} kilometres away to the {compass(bearing)}"
        up = " and upwind of this point" if upwind else ""
        out.append(
            Passage(
                passage_id=f"source-{i}",
                kind="source_upwind" if upwind else "source_nearby",
                text=(
                    f"{name.capitalize()}, a known {TYPE_LABEL.get(kind, 'emission source')},"
                    f"{where}{up}. Influence score {influence:.2f}."
                ),
                facts={
                    "name": name,
                    "type": kind,
                    "distance_km": dist,
                    "bearing_deg": bearing,
                    "influence": influence,
                    "in_upwind": upwind,
                },
                authority=0.78,
                evidence_id=ids.get("sources"),
                source_url=_osm_url(s),
            )
        )

    # ---- weather and ventilation ------------------------------------------
    if weather:
        w: dict[str, Any] = weather
        speed: float | None = w.get("wind_speed_ms")
        gust: float | None = w.get("wind_gust_ms")
        wind_from: float | None = w.get("wind_direction_deg")
        parts: list[str] = []
        if speed is not None:
            parts.append(f"Wind is {float(speed):.1f} metres per second")
        if wind_from is not None:
            parts.append(f"from the {compass(float(wind_from))}")
        if gust is not None:
            parts.append(f"with gusts to {float(gust):.1f}")
        if parts:
            out.append(
                Passage(
                    passage_id="wind",
                    kind="wind",
                    text=", ".join(parts) + ".",
                    facts={
                        "speed": speed,
                        "gust": gust,
                        "wind_from": wind_from,
                        "wind_from_label": (
                            compass(float(wind_from)) if wind_from is not None else None
                        ),
                    },
                    authority=0.8,
                    age_seconds=w.get("age_seconds"),
                    observed_at=w.get("observed_at"),
                )
            )
        # Ventilation is a derived claim, so it is labelled as such and kept
        # separate from the observation it comes from.
        if speed is not None:
            verdict, why = _ventilation(float(speed), gust)
            out.append(
                Passage(
                    passage_id="ventilation",
                    kind="ventilation",
                    text=f"Ventilation here is {verdict}: {why}.",
                    facts={"speed": speed, "verdict": verdict},
                    authority=0.7,
                )
            )

    if fires is not None:
        out.append(
            Passage(
                passage_id="fires",
                kind="fire_activity",
                text=(
                    f"{fires} satellite fire detections within the area in the last "
                    "few days."
                    if fires
                    else "No satellite fire detections near this point recently."
                ),
                facts={"count": fires},
                authority=0.6,
                evidence_id=ids.get("fires"),
            )
        )

    # ---- freshness and coverage -------------------------------------------
    age = float(getattr(estimate, "data_age_seconds", 0.0) or 0.0)
    stale = bool(getattr(estimate, "stale", False))
    out.append(
        Passage(
            passage_id="freshness",
            kind="freshness",
            text=(
                f"The inputs behind this number are {age / 3600:.0f} hours old"
                + (", which is stale." if stale else ".")
            ),
            facts={"age_seconds": age, "stale": stale},
            authority=0.9,
        )
    )
    return out


def _trend_from(stations: list[dict[str, Any]]) -> tuple[str, float, int] | None:
    """Compare the newest and oldest readings we hold for the nearest station."""
    if len(stations) < 2:
        return None
    newest = stations[0]
    oldest = stations[-1]
    a, b = newest.get("pm25"), oldest.get("pm25")
    if a is None or b is None:
        return None
    ta, tb = newest.get("observed_at"), oldest.get("observed_at")
    hours = _hours_between(tb, ta)
    delta = float(a) - float(b)
    if hours is None or hours <= 0:
        return None
    return ("rising" if delta > 0 else "falling", delta, int(hours))


def _hours_between(earlier: str | None, later: str | None) -> float | None:
    if not earlier or not later:
        return None
    try:
        a = datetime.fromisoformat(earlier)
        b = datetime.fromisoformat(later)
    except ValueError:
        return None
    if a.tzinfo is None and b.tzinfo is not None:
        a = a.replace(tzinfo=b.tzinfo)
    if b.tzinfo is None and a.tzinfo is not None:
        b = b.replace(tzinfo=a.tzinfo)
    delta = (b - a).total_seconds() / 3600.0
    return delta if delta > 0 else None


def _ventilation(speed: float, gust: float | None) -> tuple[str, str]:
    """Derived from wind speed alone; the thresholds are stated in `docs/ALGORITHM.md`."""
    effective = max(speed, float(gust or 0.0))
    if effective < 2.0:
        return ("poor", "the air is nearly still, so pollution accumulates")
    if effective < 4.0:
        return ("moderate", "there is light wind, so pollution disperses only slowly")
    return ("good", "the wind is strong enough to flush particles out")


def _openaq_url(name: str | None) -> str | None:
    if not name:
        return None
    tail = name.rsplit("-", 1)[-1]
    if not tail.isdigit():
        return None
    return (
        "https://cpcb.nic.in/RealTime/AQI_Dashboard_Station-wise.aspx"
        f"?CityID=&StateID=&CountryID=IN&StationID={tail}"
    )


def _osm_url(source: dict[str, Any]) -> str | None:
    osm_id = source.get("osm_id")
    if not osm_id or str(osm_id).startswith("static-"):
        return None
    kind = str(osm_id).split("/", 1)[0]
    if kind in {"node", "way", "relation"}:
        return f"https://www.openstreetmap.org/{kind}/{osm_id.split('/')[-1]}"
    lat = source.get("latitude")
    lon = source.get("longitude")
    if lat is not None and lon is not None:
        return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"
    return None


__all__ = ["CPCB_BAND_TEXT", "TYPE_LABEL", "build_passages", "compass", "source_name"]

/**
 * Pick the point your alerts should cover.
 *
 * The form used to offer only a dropdown of 127 named places, so someone whose
 * street is not on that list had no way to subscribe at all - which is exactly
 * the person who most wants an alert. Clicking the map accepts any coordinate in
 * the coverage area; the search box and dropdown remain as a faster route for
 * people who know the name of their locality.
 *
 * The current selection is always shown with its resolved estimate, so it is
 * obvious *which* point the alert will be about before anyone submits.
 */

import { useEffect, useRef, useState } from "react";
import type { Map as MlMap } from "maplibre-gl";
import { useTranslation } from "react-i18next";
import { allPlaces, searchPlaces, type Place } from "../../lib/places";
import { api } from "../../lib/api";

/** Closest gazetteer entry, used only to label the point ("My location near X"). */
function nearestPlace(lat: number, lon: number): Place | null {
  let best: Place | null = null;
  let bestD = Number.POSITIVE_INFINITY;
  for (const p of allPlaces()) {
    const dx = p.lon - lon;
    const dy = p.lat - lat;
    const d = dx * dx + dy * dy;
    if (d < bestD) {
      bestD = d;
      best = p;
    }
  }
  return bestD <= 0.09 ? best : null;
}

export function LocationPicker({
  value,
  onChange,
}: {
  value: Place;
  onChange: (p: Place) => void;
}) {
  const { t } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const [ready, setReady] = useState(false);
  const [query, setQuery] = useState("");
  const matches = query.trim() ? searchPlaces(query).slice(0, 6) : [];
  const [locating, setLocating] = useState(false);
  const [locNote, setLocNote] = useState<string | null>(null);

  // Superseded by any newer point: a permission complaint must never survive
  // alongside a selection that the user has since changed by another route.
  useEffect(() => {
    attempt.current += 1;
    setLocating(false);
    setLocNote(null);
  }, [value.lat, value.lon]);

  /**
   * Let the browser supply the coordinates instead of making people find their
   * own locality in a list. The point is kept verbatim - never snapped to a
   * named place - because a person standing in Ghevra wants their own street,
   * not the centroid of the Ghevra locality.
   */
  const attempt = useRef(0);

  async function useMyLocation(): Promise<void> {
    if (!navigator.geolocation) {
      setLocNote(t("subscribe.locUnavailable"));
      return;
    }
    // A permission the browser has blocked outright never prompts again, so
    // telling the user to "allow it" is only useful if we know that is the state.
    try {
      const status = await navigator.permissions?.query({ name: "geolocation" });
      if (status?.state === "denied" && navigator.permissions) {
        setLocNote(t("subscribe.locBlocked"));
        return;
      }
    } catch {
      // Permissions API is unsupported in some browsers; fall through to the
      // normal request, which will prompt or report the real reason.
    }
    setLocating(true);
    setLocNote(null);
    const mine = ++attempt.current;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        // A newer attempt has already reported; drop this stale callback.
        if (mine !== attempt.current) return;
        setLocating(false);
        const { latitude: lat, longitude: lon } = pos.coords;
        const nearest = nearestPlace(lat, lon);
        onChange({ name: `My location${nearest ? ` near ${nearest.name}` : ""}`, lat, lon });
      },
      (err) => {
        if (mine !== attempt.current) return;
        setLocating(false);
        // GeolocationPositionError.PERMISSION_DENIED is 1 per spec. Compare the
        // code rather than err.PERMISSION_DENIED, which is not guaranteed to be
        // present on every implementation of the error object.
        setLocNote(err.code === 1 ? t("subscribe.locDenied") : t("subscribe.locFailed"));
      },
      { timeout: 10000, enableHighAccuracy: true },
    );
  }
  const [estimate, setEstimate] = useState<{ mid: number; band: string } | null>(null);

  useEffect(() => {
    let disposed = false;
    let map: MlMap | null = null;
    (async () => {
      try {
        const maplibregl = (await import("maplibre-gl")).default;
        await import("maplibre-gl/dist/maplibre-gl.css");
        if (disposed || !container.current) return;
        map = new maplibregl.Map({
          container: container.current,
          style: {
            version: 8,
            sources: {
              osm: {
                type: "raster",
                tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                tileSize: 256,
                attribution: "© OpenStreetMap contributors (ODbL)",
              },
            },
            layers: [{ id: "osm", type: "raster", source: "osm" }],
          },
          center: [value.lon, value.lat],
          zoom: 11,
          attributionControl: { compact: true },
        });
        map.addControl(new maplibregl.NavigationControl(), "top-right");
        map.once("load", () => setReady(true));
        if (map.loaded()) setReady(true);
        map.on("click", (e) => {
          const picked = {
            name: `${e.lngLat.lat.toFixed(4)}, ${e.lngLat.lng.toFixed(4)}`,
            lat: e.lngLat.lat,
            lon: e.lngLat.lng,
          } satisfies Place;
          onChange(picked);
        });
        const el = container.current;
        if (el) {
          const observer = new ResizeObserver(() => {
            map!.resize();
          });
          observer.observe(el);
        }
        mapRef.current = map;
      } catch {
        /* the dropdown still works if the map cannot load */
      }
    })();
    return () => {
      disposed = true;
      map?.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // keep the pin on the current selection
  useEffect(() => {
    const map = mapRef.current;
    if (map && ready) map.flyTo({ center: [value.lon, value.lat], zoom: Math.max(map.getZoom(), 10) });
  }, [value.lat, value.lon, ready]);

  // show what the alert will actually be about
  useEffect(() => {
    let cancelled = false;
    api
      .estimate(value.lat, value.lon, false)
      .then((e) => {
        if (!cancelled) setEstimate({ mid: e.pm25_mid, band: e.category });
      })
      .catch(() => {
        if (!cancelled) setEstimate(null);
      });
    return () => {
      cancelled = true;
    };
  }, [value.lat, value.lon]);

  return (
    <div className="space-y-2" data-testid="location-picker">
      <label className="block text-sm">
        Search for a locality
        <button
          type="button"
          data-testid="picker-use-location"
          onClick={useMyLocation}
          disabled={locating}
          className="mb-2 flex min-h-touch w-full items-center justify-center gap-2 rounded bg-white/10 text-sm font-medium hover:bg-white/15 disabled:opacity-60"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden focusable="false">
            <circle cx="12" cy="12" r="3" />
            <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
            <circle cx="12" cy="12" r="8" />
          </svg>
          {locating ? t("subscribe.locating") : t("subscribe.useLocation")}
        </button>
        {locNote && (
          <p role="status" data-testid="picker-location-note" className="mb-2 text-xs text-amber-200">
            {locNote}
          </p>
        )}
        <input
          data-testid="picker-search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("picker.searchPlaceholder")}
          className="mt-1 w-full rounded bg-white/10 p-2 min-h-touch"
        />
      </label>
      {matches.length > 0 && (
        <ul className="max-h-48 overflow-auto rounded-lg border border-white/10 bg-slate-900/80">
          {matches.map((p) => (
            <li key={p.name}>
              <button
                type="button"
                className="w-full px-3 py-2 text-left text-sm hover:bg-white/10"
                onClick={() => {
                  onChange(p);
                  setQuery("");
                }}
              >
                {p.name}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div
        ref={container}
        data-testid="picker-map"
        className="h-64 w-full rounded-xl border border-white/10"
      />
      {!ready && (
        <p className="text-xs text-slate-500">Loading the map…</p>
      )}

      <div className="flex flex-wrap items-center gap-2 rounded-lg bg-slate-800/60 p-2.5 text-sm">
        <span className="text-xs uppercase tracking-wide text-slate-400">{t("picker.alertsFor")}</span>
        <span className="font-medium" data-testid="picker-selection">
          {value.name}
        </span>
        {estimate && (
          <span className="ml-auto rounded-full bg-teal-500/15 px-2 py-0.5 text-xs text-teal-200">
            {t("picker.now")} {estimate.mid.toFixed(0)} µg/m³ · {estimate.band}
          </span>
        )}
      </div>
      <p className="text-[11px] text-slate-500">
        {t("picker.tapHint")}
      </p>

      <label className="block text-sm">
        {t("picker.savedHeading")}
        <select
          data-testid="sub-place"
          value={value.name}
          onChange={(e) => {
            const found = allPlaces().find((p) => p.name === e.target.value);
            if (found) onChange(found);
          }}
          className="mt-1 w-full rounded bg-white/10 p-2 min-h-touch"
        >
          {allPlaces().map((p) => (
            <option key={p.name} value={p.name}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

export default LocationPicker;
/**
 * The source map.
 *
 * Every dot is clickable and every one of them answers a question: what is
 * this, how far, which way, how much does it matter. The previous version drew
 * circles and nothing else - hovering gave no feedback, clicking a source did
 * nothing at all, and the only click handler moved the map to an arbitrary
 * point. A map that cannot be interrogated is a picture.
 *
 * Design decisions:
 *
 * - Upwind sources and merely-nearby ones look different, because only one of
 *   those can actually explain the air at your point.
 * - Influence drives radius, so the thing that matters is visible without
 *   reading a label.
 * - The popup says plainly that influence is a heuristic ranking, not a
 *   measurement of emissions.
 * - Clicking empty map still re-centres, because picking a location by clicking
 *   it is the fastest way to move.
 */

import { useEffect, useRef, useState } from "react";
import type { Map as MlMap } from "maplibre-gl";
import type maplibregl from "maplibre-gl";


type MapLibreStatic = typeof maplibregl;
import type { SourceHit, StationReading } from "../../lib/api";
import { CATEGORY_COLORS } from "../../lib/aqi";

const UPWIND = "#f97316"; // orange - can reach you
const NEARBY = "#64748b"; // slate - close, but downwind
const CENTRE = "#2dd4bf"; // teal - the point you asked about

const TYPE_LABEL: Record<string, string> = {
  landfill: "Landfill / waste site",
  waste_disposal: "Waste site",
  industrial: "Industrial area",
  construction: "Construction site",
  major_junction: "Major junction",
  power_plant: "Power plant",
  other: "Emission source",
} as Record<string, string>;

function compass(deg: number): string {
  const points = [
    "north", "north-northeast", "northeast", "east-northeast",
    "east", "east-southeast", "southeast", "south-southeast",
    "south", "south-southwest", "southwest", "west-southwest",
    "west", "west-northwest", "northwest", "north-northwest",
  ];
  const i = Math.round((((deg % 360) + 360) % 360) / 22.5) % 16;
  return points[i] ?? "north";
}

/** Popup for a live station: the observed reading behind an estimate. */
/** Category colour with a guaranteed fallback, for use in paint expressions. */
function catColour(cat: string): string {
  return CATEGORY_COLORS[cat] ?? "#64748b";
}

function stationPopupHtml(st: {
  name: string;
  pm25: number | null;
  category: string;
  distance_km: number;
  age_seconds: number | null;
}): string {
  const esc = (v: string): string =>
    v.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const colour = CATEGORY_COLORS[st.category] ?? "#64748b";
  const ageH =
    st.age_seconds == null
      ? null
      : Math.round(st.age_seconds / 3600);
  return `
    <div style="font-family:system-ui,sans-serif;color:#e2e8f0;font-size:12px">
      <div style="font-weight:600;font-size:13px;margin-bottom:4px">${esc(st.name)}</div>
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
        <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${colour}"></span>
        <span style="font-family:ui-monospace,monospace;font-size:16px;font-weight:700">${
          st.pm25 == null ? "no reading" : `${st.pm25.toFixed(0)} µg/m³`
        }</span>
        ${st.category ? `<span style="color:${colour}">${esc(st.category)}</span>` : ""}
      </div>
      <div style="color:#94a3b8">${st.distance_km.toFixed(2)} km from your point</div>
      ${
        ageH == null
          ? ""
          : `<div style="color:#fbbf24">Observed ${ageH} h ago${
              ageH > 36 ? " — this archive is stale" : ""
            }</div>`
      }
      <div style="color:#64748b;margin-top:5px;border-top:1px solid #1e293b;padding-top:5px">
        This is a real station reading, not our estimate. The estimate uses it as
        its anchor and adjusts from there.
      </div>
    </div>`;
}

function osmLink(id: string): string | null {
  const [kind, ref] = id.split("/");
  if (kind && ref && ["node", "way", "relation"].includes(kind)) {
    return `https://www.openstreetmap.org/${kind}/${ref}`;
  }
  return null;
}

interface Props {
  lat: number;
  lon: number;
  sources: SourceHit[];
  windFromDeg?: number | null;
  onPick: (lat: number, lon: number) => void;
  stations?: StationReading[];
  className?: string;
}

export function SourceMap({
  lat,
  lon,
  sources,
  windFromDeg,
  onPick,
  stations = [],
  className = "",
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const mlRef = useRef<MapLibreStatic | null>(null);
  const sourcesRef = useRef<SourceHit[]>(sources);
  sourcesRef.current = sources;
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;

  // Which layers the reader wants to see. A map with three overlapping classes
  // of marker is unreadable at Delhi scale, so each can be switched off.
  const [layers, setLayers] = useState({ sources: true, stations: true });
  const [compareOn, setCompareOn] = useState(false);
  const [comparePoint, setComparePoint] = useState<{ lat: number; lon: number } | null>(null);
  const [cursor, setCursor] = useState<{ lat: number; lon: number } | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  const layersRef = useRef(layers);
  layersRef.current = layers;
  const compareOnRef = useRef(compareOn);
  compareOnRef.current = compareOn;
  const comparePointRef = useRef(comparePoint);
  comparePointRef.current = comparePoint;

  const toggle = (k: "sources" | "stations"): void =>
    setLayers((prev) => ({ ...prev, [k]: !prev[k] }));

  useEffect(() => {
    let disposed = false;
    let map: MlMap | null = null;
    (async () => {
      try {
        const maplibregl = (await import("maplibre-gl")).default;
        await import("maplibre-gl/dist/maplibre-gl.css");
        mlRef.current = maplibregl;
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
          center: [lon, lat],
          zoom: 11,
          attributionControl: { compact: true },
        });
        map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "bottom-right");
        // A single missing tile, a rate-limit, or a bad glyph request must not
        // destroy an otherwise usable map - it previously replaced the whole map
        // with an error panel, which is how one transient tile fault made the
        // map look completely broken. Only a failure to load the style itself is
        // treated as fatal; everything else degrades to blank tiles.
        map.on("error", (e: { error?: Error; sourceId?: string }) => {
          const message = String(e?.error?.message ?? "");
          const fatal = !e?.sourceId && /style|glyph|sprite/i.test(message);
          if (fatal) setFailed(true);
        });

        // ONE handler, bound when the map is created, that hit-tests the layers
        // itself. Layer-delegated listeners are the fragile path: MapLibre
        // drops them if the layer is missing at bind time, and they were being
        // skipped by an early return on every re-render. A single map-level
        // listener that calls queryRenderedFeatures has neither problem.
        map.on("click", (e) => {
          // A station marker wins over the source layer when both are hit, and
          // only when the reader has stations switched on.
          if (layersRef.current.stations && live.getLayer("station-dot")) {
            const stHits = live.queryRenderedFeatures(e.point, { layers: ["station-dot"] });
            const sf = stHits[0];
            if (sf && sf.geometry.type === "Point") {
              const sp = sf.properties as unknown as Record<string, unknown>;
              new maplibregl.Popup({ offset: 12, maxWidth: "280px" })
                .setLngLat(sf.geometry.coordinates as [number, number])
                .setHTML(stationPopupHtml({
                  name: String(sp.name ?? ""),
                  pm25: sp.pm25 == null ? null : Number(sp.pm25),
                  category: String(sp.category ?? ""),
                  distance_km: Number(sp.distance_km ?? 0),
                  age_seconds: sp.age_seconds == null ? null : Number(sp.age_seconds),
                }))
                .addTo(live);
              return;
            }
          }
          const hits = live.queryRenderedFeatures(e.point, {
            layers: ["source-dots", "source-halo"],
          });
          if (!hits.length) {
            // In compare mode the first click sets the second point; the reader
            // then pans and clicks again to set the first one.
            if (compareOnRef.current) {
              if (comparePointRef.current === null) {
                setComparePoint({ lat: e.lngLat.lat, lon: e.lngLat.lng });
              } else {
                onPickRef.current(e.lngLat.lat, e.lngLat.lng);
              }
            } else {
              onPickRef.current(e.lngLat.lat, e.lngLat.lng);
            }
            return;
          }
          const f = hits[0]!;
          if (f.geometry.type !== "Point") return;
          // GeoJSON properties are flat and renamed for the paint expressions,
          // so map them back onto the API shape rather than assuming they match.
          const raw = f.properties as unknown as Record<string, unknown>;
          const props: SourceHit = {
            osm_id: String(raw.osm_id ?? ""),
            type: String(raw.type ?? "other"),
            name: String(raw.name ?? ""),
            latitude: 0,
            longitude: 0,
            distance_km: Number(raw.distance_km ?? 0),
            bearing_deg: Number(raw.bearing_deg ?? 0),
            influence_score: Number(raw.influence ?? 0),
            in_upwind_cone: raw.in_upwind === true || raw.in_upwind === "true",
            area_m2: raw.area_m2 == null ? null : Number(raw.area_m2),
            attribution: "",
          };
          new maplibregl.Popup({ offset: 14, maxWidth: "290px" })
            .setLngLat(f.geometry.coordinates as [number, number])
            .setHTML(popupHtml(props))
            .addTo(live);
        });
        map.on("mousemove", (e) => {
          const overSource = live.queryRenderedFeatures(e.point, {
            layers: ["source-dots", "source-halo"],
          }).length > 0;
          const overStation =
            layersRef.current.stations &&
            live.getLayer("station-dot") !== undefined &&
            live.queryRenderedFeatures(e.point, { layers: ["station-dot"] }).length > 0;
          live.getCanvas().style.cursor = overSource || overStation ? "pointer" : "";
          setCursor({ lat: e.lngLat.lat, lon: e.lngLat.lng });
        });
        map.on("mouseout", () => setCursor(null));
        mapRef.current = map;
        map.once("load", () => setReady(true));
        if (map.loaded()) setReady(true);

        const live = map;
        const el = container.current;
        if (el) {
          const observer = new ResizeObserver(() => {
            live.resize();
            live.triggerRepaint();
          });
          observer.observe(el);
        }
      } catch {
        setFailed(true);
      }
    })();
    return () => {
      disposed = true;
      map?.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    void (async () => {
    const geojson: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: sources.map((s, i) => ({
        type: "Feature",
        id: i,
        properties: {
          name: s.name,
          type: s.type,
          type_label: TYPE_LABEL[s.type] ?? TYPE_LABEL.other!,
          distance_km: s.distance_km,
          bearing_deg: s.bearing_deg,
          influence: s.influence_score,
          in_upwind: s.in_upwind_cone,
          area_m2: s.area_m2,
          osm_id: s.osm_id,
        },
        geometry: { type: "Point", coordinates: [s.longitude, s.latitude] },
      })),
    };
    const src = map.getSource("sources") as import("maplibre-gl").GeoJSONSource | undefined;
    if (src) {
      // The layers already exist: just refresh the data. Returning here is what
      // broke the popups - the click handlers were bound below this point, so
      // every re-render skipped them and the dots stopped responding entirely.
      src.setData(geojson);
      return;
    }
    map.addSource("sources", { type: "geojson", data: geojson });
    map.addLayer({
      id: "source-dots",
      type: "circle",
      source: "sources",
      paint: {
        "circle-radius": [
          "interpolate", ["linear"], ["get", "influence"],
          0, 5, 0.4, 9, 1, 16,
        ],
        "circle-color": [
          "case", ["get", "in_upwind"], UPWIND, NEARBY,
        ],
        "circle-opacity": 0.9,
        "circle-stroke-width": 2,
        "circle-stroke-color": "#0f172a",
      },
    });
    map.addLayer({
      id: "source-halo",
      type: "circle",
      source: "sources",
      paint: {
        "circle-radius": [
          "interpolate", ["linear"], ["get", "influence"],
          0, 9, 0.4, 14, 1, 22,
        ],
        "circle-color": [
          "case", ["get", "in_upwind"], UPWIND, NEARBY,
        ],
        "circle-opacity": 0.18,
        "circle-blur": 0.5,
      },
    });
    map.addSource("centre", {
      type: "geojson",
      data: {
        type: "Feature",
        properties: {},
        geometry: { type: "Point", coordinates: [lon, lat] },
      },
    });
    map.addLayer({
      id: "centre-dot",
      type: "circle",
      source: "centre",
      paint: {
        "circle-radius": 7,
        "circle-color": CENTRE,
        "circle-stroke-width": 3,
        "circle-stroke-color": "#0f172a",
      },
    });
    })().catch((err) => console.error("source layer setup failed", err));
  }, [sources, ready, lat, lon]);


  // Live monitoring stations. These are what the estimate is anchored to, so
  // showing them turns "our estimate" into something checkable: you can see the
  // actual reading behind it and how far away that station is.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    void (async () => {
      const geojson: GeoJSON.FeatureCollection = {
        type: "FeatureCollection",
        features: stations.map((st) => ({
          type: "Feature",
          properties: {
            station_id: st.station_id,
            name: st.name,
            pm25: st.pm25 == null ? null : st.pm25,
            category: st.category ?? "",
            distance_km: st.distance_km,
            age_seconds: st.age_seconds,
          },
          geometry: { type: "Point", coordinates: [st.longitude, st.latitude] },
        })),
      };
      const existing = map.getSource("stations") as
        | import("maplibre-gl").GeoJSONSource
        | undefined;
      if (existing) {
        existing.setData(geojson);
        return;
      }
      map.addSource("stations", { type: "geojson", data: geojson });
      map.addLayer({
        id: "station-halo",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": 9,
          "circle-color": [
            "case",
            ["==", ["get", "category"], "Good"], catColour("Good"),
            ["==", ["get", "category"], "Satisfactory"], catColour("Satisfactory"),
            ["==", ["get", "category"], "Moderately Polluted"], catColour("Moderately Polluted"),
            ["==", ["get", "category"], "Poor"], catColour("Poor"),
            ["==", ["get", "category"], "Very Poor"], catColour("Very Poor"),
            catColour("Severe"),
          ],
          "circle-opacity": 0.22,
        },
      });
      map.addLayer({
        id: "station-dot",
        type: "circle",
        source: "stations",
        paint: {
          // bigger marker = higher reading, so the pattern is visible without
          // needing a text layer (which would require a font server)
          "circle-radius": [
            "interpolate", ["linear"], ["coalesce", ["to-number", ["get", "pm25"]], 0],
            0, 3, 50, 5, 150, 7, 300, 9,
          ],
          "circle-color": [
            "case",
            ["==", ["get", "category"], "Good"], catColour("Good"),
            ["==", ["get", "category"], "Satisfactory"], catColour("Satisfactory"),
            ["==", ["get", "category"], "Moderately Polluted"], catColour("Moderately Polluted"),
            ["==", ["get", "category"], "Poor"], catColour("Poor"),
            ["==", ["get", "category"], "Very Poor"], catColour("Very Poor"),
            catColour("Severe"),
          ],
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#0f172a",
        },
      });
    })().catch(() => undefined);
  }, [stations, ready]);

  // Visibility is driven by the toggles without rebuilding the sources.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const id of ["source-dots", "source-halo"]) {
      if (map.getLayer(id))
        map.setLayoutProperty(id, "visibility", layers.sources ? "visible" : "none");
    }
    for (const id of ["station-dot", "station-halo"]) {
      if (map.getLayer(id))
        map.setLayoutProperty(id, "visibility", layers.stations ? "visible" : "none");
    }
  }, [layers, ready]);

  // Compare mode draws the leg between the two points so the distance being
  // compared is visible rather than implied.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const data: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features:
        compareOn && comparePoint
          ? [
              {
                type: "Feature",
                properties: {},
                geometry: {
                  type: "LineString",
                  coordinates: [
                    [comparePoint.lon, comparePoint.lat],
                    [lon, lat],
                  ],
                },
              },
            ]
          : [],
    };
    const existing = map.getSource("compare") as
      | import("maplibre-gl").GeoJSONSource
      | undefined;
    if (existing) {
      existing.setData(data);
      return;
    }
    map.addSource("compare", { type: "geojson", data });
    map.addLayer({
      id: "compare-line",
      type: "line",
      source: "compare",
      paint: { "line-color": "#a78bfa", "line-width": 2, "line-dasharray": [2, 2] },
    });
  }, [compareOn, comparePoint, lat, lon, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (map && ready) {
      map.flyTo({ center: [lon, lat], zoom: Math.max(map.getZoom(), 11) });
      const centre = map.getSource("centre") as import("maplibre-gl").GeoJSONSource | undefined;
      centre?.setData({
        type: "Feature",
        properties: {},
        geometry: { type: "Point", coordinates: [lon, lat] },
      });
    }
  }, [lat, lon, ready]);

  useEffect(() => {
    if (!compareOn) setComparePoint(null);
  }, [compareOn]);

  const upwindCount = sources.filter((s) => s.in_upwind_cone).length;
  const nearestStation = stations.length > 0 ? stations[0] : null;

  const km = (a: { lat: number; lon: number }, b: { lat: number; lon: number }): number => {
    const R = 6371;
    const dLat = ((b.lat - a.lat) * Math.PI) / 180;
    const dLon = ((b.lon - a.lon) * Math.PI) / 180;
    const s =
      Math.sin(dLat / 2) ** 2 +
      Math.cos((a.lat * Math.PI) / 180) *
        Math.cos((b.lat * Math.PI) / 180) *
        Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(s));
  };

  const btn =
    "flex min-h-touch items-center gap-1.5 rounded-md px-2 py-1.5 text-[11px] font-medium shadow-lg transition-colors";
  const chipOn = "bg-teal-600/90 text-white ring-1 ring-teal-300/60";
  const chipOff = "bg-night-900/90 text-slate-300 ring-1 ring-white/10 hover:bg-night-800/95";

  return (
    <div
      ref={wrapRef}
      className={`relative h-full w-full overflow-hidden ${
        fullscreen ? "fixed inset-0 z-50 h-[100dvh] w-screen rounded-none" : "rounded-xl"
      } ${className}`}
    >
      <div ref={container} data-testid="map" className="h-full w-full" />

      {/* ---- toolbar: what is shown, plus the two view actions ---- */}
      <div
        className="absolute left-2 top-2 z-10 flex max-w-[calc(100%-1rem)] flex-wrap items-start gap-1"
        data-testid="map-toolbar"
      >
        <button
          type="button"
          data-testid="map-toggle-sources"
          aria-pressed={layers.sources}
          onClick={() => toggle("sources")}
          className={`${btn} ${layers.sources ? chipOn : chipOff}`}
        >
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: UPWIND }}
          />
          Sources
        </button>
        <button
          type="button"
          data-testid="map-toggle-stations"
          aria-pressed={layers.stations}
          onClick={() => toggle("stations")}
          className={`${btn} ${layers.stations ? chipOn : chipOff}`}
        >
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: catColour("Poor") }}
          />
          Stations
        </button>
        <button
          type="button"
          data-testid="map-toggle-compare"
          aria-pressed={compareOn}
          onClick={() => setCompareOn((v) => !v)}
          className={`${btn} ${compareOn ? chipOn : chipOff}`}
        >
          Compare two points
        </button>
        <button
          type="button"
          data-testid="map-fullscreen"
          aria-pressed={fullscreen}
          onClick={() => setFullscreen((v) => !v)}
          className={`${btn} ${chipOff}`}
        >
          {fullscreen ? "Exit full screen" : "Full screen"}
        </button>
      </div>

      {/* ---- cursor readout: where am I pointing ---- */}
      {cursor && (
        <div
          className="pointer-events-none absolute bottom-2 right-2 z-10 rounded-md bg-night-900/85 px-2 py-1 font-mono text-[10px] text-slate-300"
          data-testid="map-cursor"
        >
          {cursor.lat.toFixed(4)}, {cursor.lon.toFixed(4)}
        </div>
      )}

      {/* ---- compare instructions / measured distance ---- */}
      {compareOn && (
        <div
          className="absolute left-2 top-14 z-10 max-w-[15rem] rounded-lg bg-night-900/92 px-2.5 py-2 text-[11px] text-slate-200 shadow-lg"
          data-testid="map-compare-hint"
          role="status"
        >
          {comparePoint === null ? (
            <>Click the map to drop the second point.</>
          ) : (
            <>
              <div className="font-medium">
                {km(comparePoint, { lat, lon }).toFixed(2)} km apart
              </div>
              <div className="text-slate-400">
                Click again to move your main point here.
              </div>
              <button
                type="button"
                onClick={() => setComparePoint(null)}
                className="mt-1 underline text-slate-300"
              >
                Clear
              </button>
            </>
          )}
        </div>
      )}

      {/* ---- what the estimate is anchored to ---- */}
      {nearestStation && (
        <div
          className="pointer-events-none absolute bottom-2 left-1/2 z-10 -translate-x-1/2 rounded-lg bg-night-900/85 px-2.5 py-1.5 text-[11px] text-slate-200"
          data-testid="map-anchor"
        >
          Anchored to{" "}
          <span className="font-medium">
            {nearestStation.pm25 == null ? "—" : nearestStation.pm25.toFixed(0)}
          </span>{" "}
          µg/m³ at {nearestStation.distance_km.toFixed(1)} km
        </div>
      )}

      {!ready && !failed && (
        <div
          className="absolute inset-0 grid place-items-center bg-night-900/80 text-slate-300 text-sm"
          role="status"
        >
          Loading map…
        </div>
      )}
      {failed && (
        <div
          className="absolute inset-0 grid place-items-center bg-night-900/90 p-4 text-center text-amber-300 text-sm"
          role="alert"
        >
          The map tiles could not load. The estimate and explanation on the right
          do not depend on the map.
        </div>
      )}

      {/* Legend: the colours mean something, so say what. */}
      <div
        className="pointer-events-none absolute bottom-2 left-2 z-10 max-w-[13rem] space-y-1 rounded-lg bg-night-900/90 px-2.5 py-2 text-[11px] text-slate-200 shadow-lg"
        data-testid="map-legend"
      >
        <p className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: UPWIND }} />
          Upwind ({upwindCount}) — can reach you
        </p>
        <p className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: NEARBY }} />
          Nearby ({sources.length - upwindCount}) — downwind
        </p>
        <p className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: CENTRE }} />
          Your point
        </p>
        <p className="pt-0.5 text-[10px] text-slate-400">
          Bigger dot = higher influence. Click one for detail.
        </p>
        {windFromDeg != null && (
          <p className="text-[10px] text-slate-400">Wind from the {compass(windFromDeg)}.</p>
        )}
      </div>
    </div>
  );
}

function popupHtml(raw: SourceHit): string {
  // GeoJSON serialises feature properties to strings, so every numeric field
  // arrives as "1.5" or even "" for a null. Coerce once here instead of
  // letting toFixed throw on undefined - which it did, silently killing the
  // popup and leaving a dot that looked dead.
  const num = (v: unknown, fallback = 0) => {
    const n = typeof v === "number" ? v : Number(v);
    return Number.isFinite(n) ? n : fallback;
  };
  const s: SourceHit = {
    ...raw,
    distance_km: num(raw.distance_km),
    bearing_deg: num(raw.bearing_deg),
    influence_score: num(raw.influence_score),
    area_m2: raw.area_m2 == null ? null : num(raw.area_m2),
    name: String(raw.name ?? ""),
    type: String(raw.type ?? "other"),
  };
  const up = s.in_upwind_cone;
  const link = osmLink(s.osm_id);
  const area =
    typeof s.area_m2 === "number" && s.area_m2 > 0
      ? `<div>Footprint: ${Math.round(s.area_m2).toLocaleString()} m²</div>`
      : "";
  return `
    <div style="font-family:system-ui,sans-serif;font-size:12px;line-height:1.5;color:#0f172a">
      <div style="font-weight:600;font-size:13px;margin-bottom:2px">${escapeHtml(
        s.name && s.name !== s.type && s.name.toLowerCase() !== TYPE_LABEL[s.type]?.toLowerCase()
          ? s.name
          : (TYPE_LABEL[s.type] ?? "Emission source"),
      )}</div>
      <div style="color:#475569;margin-bottom:6px">${escapeHtml(
        s.name && s.name.toLowerCase() !== TYPE_LABEL[s.type]?.toLowerCase()
          ? (TYPE_LABEL[s.type] ?? "")
          : "",
      )}</div>
      <div><b>${s.distance_km.toFixed(2)} km</b> away, to the ${compass(s.bearing_deg)}</div>
      <div>Influence score <b>${s.influence_score.toFixed(2)}</b> / 1.00</div>
      ${area}
      <div style="margin-top:6px;padding:4px 6px;border-radius:4px;background:${
        up ? "#fff7ed" : "#f1f5f9"
      };color:${up ? "#9a3412" : "#334155"}">
        ${
          up
            ? "Upwind — air from here can reach your point."
            : "Downwind — this source cannot explain the air at your point."
        }
      </div>
      ${
        link
          ? `<a href="${link}" target="_blank" rel="noreferrer" style="display:inline-block;margin-top:6px;color:#0f766e">View on OpenStreetMap →</a>`
          : ""
      }
      <div style="margin-top:6px;color:#64748b;font-size:11px">
        Influence is a heuristic ranking from distance, bearing and type. It is
        not a measurement of emissions.
      </div>
    </div>`;
}

function escapeHtml(raw: string): string {
  return raw.replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!,
  );
}

export default SourceMap;
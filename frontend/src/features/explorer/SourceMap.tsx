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
import type { SourceHit } from "../../lib/api";

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

function osmLink(id: string): string | null {
  const [kind, ref] = id.split("/");
  if (kind && ref && ["node", "way", "relation"].includes(kind)) {
    return `https://www.openstreetmap.org/${kind}/${ref}`;
  }
  return null;
}

export function SourceMap({
  lat,
  lon,
  sources,
  windFromDeg,
  onPick,
  className = "",
}: {
  lat: number;
  lon: number;
  sources: SourceHit[];
  windFromDeg?: number | null;
  onPick: (lat: number, lon: number) => void;
  className?: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const mlRef = useRef<MapLibreStatic | null>(null);
  const sourcesRef = useRef<SourceHit[]>(sources);
  sourcesRef.current = sources;
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;

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
        map.addControl(new maplibregl.NavigationControl(), "top-right");
        map.on("error", () => setFailed(true));

        // ONE handler, bound when the map is created, that hit-tests the layers
        // itself. Layer-delegated listeners are the fragile path: MapLibre
        // drops them if the layer is missing at bind time, and they were being
        // skipped by an early return on every re-render. A single map-level
        // listener that calls queryRenderedFeatures has neither problem.
        map.on("click", (e) => {
          const hits = live.queryRenderedFeatures(e.point, {
            layers: ["source-dots", "source-halo"],
          });
          if (!hits.length) {
            onPickRef.current(e.lngLat.lat, e.lngLat.lng);
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
          const over = live.queryRenderedFeatures(e.point, {
            layers: ["source-dots", "source-halo"],
          }).length > 0;
          live.getCanvas().style.cursor = over ? "pointer" : "";
        });
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

  const upwindCount = sources.filter((s) => s.in_upwind_cone).length;

  return (
    <div className={`relative h-full w-full overflow-hidden rounded-xl ${className}`}>
      <div ref={container} data-testid="map" className="h-full w-full" />

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
        className="pointer-events-none absolute bottom-2 left-2 space-y-1 rounded-lg bg-night-900/85 px-2.5 py-2 text-[11px] text-slate-200"
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
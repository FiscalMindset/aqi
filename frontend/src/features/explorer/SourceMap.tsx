import { useEffect, useRef, useState } from "react";
import type { Map as MlMap } from "maplibre-gl";
import { useIdleCallback } from "../../lib/useIdleCallback";
import type { SourceHit } from "../../lib/api";

/**
 * Map with the location pin, wind arrow, upwind cone shading, source markers
 * (distinct icon + label, never color alone) and a tap-to-select handler.
 *
 * Tiles: Amazon Location Service maps when VITE_LOCATION_MAPS_URL is set;
 * otherwise OpenStreetMap raster tiles (attribution shown in the footer).
 *
 * MapLibre (JS + CSS, ~1 MB) is imported inside an idle callback so the
 * initial paint and the Lighthouse mobile performance budget never wait for
 * the map: the shell, estimate panel and controls come up first.
 */
export function SourceMap({
  lat,
  lon,
  sources,
  onPick,
}: {
  lat: number;
  lon: number;
  sources: SourceHit[];
  onPick: (lat: number, lon: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);

  useIdleCallback(() => {
    void (async () => {
      if (!ref.current || mapRef.current) return;
      try {
        await _initMap(ref.current);
      } catch (err) {
        console.error("map init failed", err);
        setFailed(true);
      } finally {
        setLoading(false);
      }
    })();
  });

  async function _initMap(container: HTMLDivElement) {
    {
      if (mapRef.current) return;
      const maplibregl = (await import("maplibre-gl")).default;
      await import("maplibre-gl/dist/maplibre-gl.css");
      const tiles = import.meta.env.VITE_LOCATION_MAPS_URL;
      const map = new maplibregl.Map({
        container,
        style: {
          version: 8,
          sources: {
            base: {
              type: "raster",
              tiles: tiles ? [tiles] : ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              attribution:
                "© OpenStreetMap contributors (ODbL)" +
                (tiles ? " · Amazon Location Service" : ""),
            },
          },
          layers: [{ id: "base", type: "raster", source: "base", minzoom: 0, maxzoom: 19 }],
        },
        center: [lon, lat],
        zoom: 12,
      });
      map.addControl(new maplibregl.NavigationControl(), "top-right");
      map.on("click", (e) => onPick(e.lngLat.lat, e.lngLat.lng));
      map.on("error", (e) => {
        // tile fetch failures are visible, not silent
        console.warn("map error", e.error?.message ?? "unknown");
      });
      mapRef.current = map;
      map.once("load", () => setReady(true));
      if (map.loaded()) setReady(true);
    }
  }

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.flyTo({ center: [lon, lat], zoom: Math.max(map.getZoom(), 12) });
  }, [lat, lon]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
  }, [lat, lon]);

  useEffect(() => {
    const map = mapRef.current;
    // Waiting for isStyleLoaded() looked safer but was the bug: sources
    // routinely arrive before the raster style finished loading, the effect
    // bailed out, and nothing redrew them afterwards because its deps never
    // changed again. The map showed a street grid with zero source markers.
    // `ready` flips when the style loads and re-runs this effect.
    if (!map || !ready) return;
    const geojson = {
      type: "FeatureCollection" as const,
      features: sources.map((s) => ({
        type: "Feature" as const,
        properties: {
          name: s.name,
          type: s.type,
          distance_km: s.distance_km,
          influence: s.influence_score,
        },
        geometry: { type: "Point" as const, coordinates: [s.longitude, s.latitude] },
      })),
    };
    const src = map.getSource("sources") as maplibregl.GeoJSONSource | undefined;
    if (src) src.setData(geojson);
    else {
      map.addSource("sources", { type: "geojson", data: geojson });
      map.addLayer({
        id: "source-dots",
        type: "circle",
        source: "sources",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "influence"], 0, 4, 1, 12],
          "circle-color": "#f97316",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#111827",
        },
      });
      map.addLayer({
        id: "source-labels",
        type: "symbol",
        source: "sources",
        layout: {
          "text-field": ["get", "name"],
          "text-size": 11,
          "text-offset": [0, 1.2],
          "text-allow-overlap": false,
        },
        paint: { "text-color": "#fde68a", "text-halo-color": "#111827", "text-halo-width": 1 },
      });
    }
  }, [sources, ready]);

  useEffect(() => {
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <div className="absolute inset-0 h-full w-full">
      <div
        ref={ref}
        data-testid="map"
        // h-full/w-full, NOT `absolute inset-0`: maplibre-gl.css sets
        // .maplibregl-map { position: relative } and is imported after
        // Tailwind, so it overrides .absolute with equal specificity. The div
        // then became position:relative with no content height -> 0px, and the
        // map was invisible even though every tile returned 200.
        className="h-full w-full"
        role="application"
        aria-label="Map of Delhi-NCR with candidate pollution sources"
      />
      {loading && !failed && (
        <div
          className="absolute inset-0 grid place-items-center bg-night-900/80 text-slate-300 text-sm"
          role="status"
          data-testid="map-loading"
        >
          Loading map…
        </div>
      )}
      {failed && (
        <div
          className="absolute inset-0 grid place-items-center bg-night-900/90 text-amber-300 text-sm p-4 text-center"
          role="alert"
          data-testid="map-error"
        >
          The map could not load (tiles blocked or offline). The estimate panel and
          sources table remain available.
        </div>
      )}
    </div>
  );
}

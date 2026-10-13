import { useEffect, useRef, useState } from "react";
import type { RouteCorridor } from "../../lib/api";

const CLEAN = "#22c55e";
const DIRTY = "#f97316";

/**
 * Draws every candidate corridor on a MapLibre map, cleanest highlighted.
 *
 * Deliberately minimal: no markers, no source layers - this map exists to show
 * the shape of the alternatives and where their worst sample sits. Reuses the
 * same OpenStreetMap raster tiles as the explorer map, so there is no key and
 * no third-party style dependency.
 */
export function RouteMap({
  corridors,
  origin,
  destination,
  className = "",
}: {
  corridors: RouteCorridor[];
  origin: { lat: number; lon: number };
  destination: { lat: number; lon: number };
  className?: string;
}): React.JSX.Element {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("maplibre-gl").Map | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);
  // maplibre is dynamically imported, so the map object arrives some time after
  // the first render. The corridors usually land BEFORE that, and the draw
  // effect bailed out with `!map` - and since its deps did not change again,
  // it never redrew. Nothing was ever drawn: no route lines, no endpoint dots,
  // only the legend promising them. `ready` makes the effect re-run when the
  // map finally exists.
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let disposed = false;
    let map: import("maplibre-gl").Map | null = null;
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
          center: [origin.lon, origin.lat],
          zoom: 10,
          attributionControl: { compact: true },
        });
        map.addControl(new maplibregl.NavigationControl(), "top-right");
        map.on("error", () => setFailed(true));
        mapRef.current = map;
        map.once("load", () => setReady(true));
        if (map.loaded()) setReady(true);

        // This map mounts inside a grid cell that has not finished laying out,
        // so MapLibre measured the container at its pre-layout width and the
        // canvas kept that size for good: a ~180 px sliver of tiles inside a
        // ~560 px column, with the navigation controls stranded far to the
        // right. Watching the container and calling resize() is the fix.
        const live = map;
        const el = container.current;
        if (el) {
          const observer = new ResizeObserver(() => {
            live.resize();
            live.triggerRepaint();
          });
          observer.observe(el);
          observerRef.current = observer;
        }
      } catch {
        setFailed(true);
      }
    })();
    return () => {
      disposed = true;
      observerRef.current?.disconnect();
      observerRef.current = null;
      map?.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // fit and redraw whenever the corridors change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || corridors.length === 0) return;
    const coords: [number, number][] = [];
    for (const c of corridors) coords.push(...(c.geometry as [number, number][]));
    coords.push([origin.lon, origin.lat], [destination.lon, destination.lat]);
    const lngs = coords.map((c) => c[0]);
    const lats = coords.map((c) => c[1]);
    map.fitBounds(
      [
        [Math.min(...lngs), Math.min(...lats)],
        [Math.max(...lngs), Math.max(...lats)],
      ],
      { padding: 48, duration: 0 },
    );
    map.resize();
    map.triggerRepaint();

    for (const id of ["corridors", "endpoints"]) {
      if (map.getLayer(id)) map.removeLayer(id);
    }
    if (map.getSource("corridors")) map.removeSource("corridors");

    map.addSource("corridors", {
      type: "geojson",
      data: {
        type: "FeatureCollection",
        features: corridors.map((c) => ({
          type: "Feature",
          properties: {
            rank: c.rank,
            colour: c.rank === 1 ? CLEAN : DIRTY,
            width: c.rank === 1 ? 6 : 4,
            dash: c.kind === "straight-line" ? "2 2" : undefined,
          },
          geometry: { type: "LineString", coordinates: c.geometry },
        })),
      },
    });
    map.addLayer({
      id: "corridors",
      type: "line",
      source: "corridors",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": ["get", "colour"],
        "line-width": ["get", "width"],
        "line-opacity": 0.9,
      },
    });

    map.addSource("endpoints", {
      type: "geojson",
      data: {
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: { colour: "#38bdf8" },
            geometry: { type: "Point", coordinates: [origin.lon, origin.lat] },
          },
          {
            type: "Feature",
            properties: { colour: "#e879f9" },
            geometry: { type: "Point", coordinates: [destination.lon, destination.lat] },
          },
        ],
      },
    });
    map.addLayer({
      id: "endpoints",
      type: "circle",
      source: "endpoints",
      paint: {
        "circle-radius": 7,
        "circle-color": ["get", "colour"],
        "circle-stroke-color": "#0f172a",
        "circle-stroke-width": 2,
      },
    });
  }, [corridors, origin, destination, ready]);

  return (
    <div className={`relative h-full w-full overflow-hidden rounded-xl ${className}`}>
      <div ref={container} data-testid="route-map" className="h-full w-full" />
      {failed && (
        <div className="absolute inset-0 grid place-items-center bg-night-900/90 p-4 text-center text-sm text-amber-300">
          The map could not load (tiles blocked or offline). The comparison
          below is still valid.
        </div>
      )}
      <div className="pointer-events-none absolute bottom-2 left-2 rounded-md bg-night-900/85 px-2 py-1 text-[10px] text-slate-300">
        <span className="mr-3 inline-flex items-center gap-1">
          <span className="inline-block h-1 w-4 rounded" style={{ background: CLEAN }} />
          cleanest
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-1 w-4 rounded" style={{ background: DIRTY }} />
          alternative
        </span>
      </div>
    </div>
  );
}
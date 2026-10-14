import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useRouteCompare } from "../../hooks/useApi";
import { allPlaces, type Place } from "../../lib/places";
import type { RouteCorridor } from "../../lib/api";
import { RouteMap } from "./RouteMap";

/**
 * A pending card that shows it is alive.
 *
 * Route comparison genuinely takes tens of seconds on a cold start: it calls
 * the routing service, then runs the estimator along every corridor. A static
 * "loading…" reads as frozen, which is exactly how this page looked broken. An
 * elapsed counter plus an honest note about what is slow turns a wait into
 * information.
 */
function PendingCard(): React.JSX.Element {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setSeconds((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);
  const slow = seconds >= 8;
  return (
    <div
      data-testid="routes-loading"
      role="status"
      aria-live="polite"
      className="rounded-xl border border-amber-500/30 bg-slate-900/60 p-8 text-center text-sm"
    >
      <div className="mx-auto mb-3 h-1 w-40 overflow-hidden rounded-full bg-slate-700">
        <div className="h-full w-1/3 animate-pulse rounded-full bg-amber-400/80" />
      </div>
      <p className="text-slate-300">
        Finding real roads and estimating the air along them…
      </p>
      <p className="mt-1 font-mono text-xs text-slate-500">
        {seconds}s elapsed
      </p>
      {slow && (
        <p className="mx-auto mt-3 max-w-md text-xs leading-relaxed text-amber-200/90">
          This is genuinely slow the first time a route is requested: the
          routing service has to answer, and then every corridor is sampled and
          estimated one point at a time. It normally lands within thirty
          seconds. You can leave this page open — it is working.
        </p>
      )}
    </div>
  );
}

/** CPCB band colour, same scale the rest of the app uses. */
function bandColour(pm25: number): string {
  if (pm25 <= 30) return "#1a9850";
  if (pm25 <= 60) return "#91cf60";
  if (pm25 <= 90) return "#fee08b";
  if (pm25 <= 120) return "#fc8d59";
  if (pm25 <= 250) return "#d73027";
  return "#7f0000";
}

function PlaceSelect({
  label,
  value,
  onChange,
  testId,
}: {
  label: string;
  value: Place;
  onChange: (p: Place) => void;
  testId: string;
}): React.JSX.Element {
  return (
    <label className="flex-1 text-xs text-slate-400">
      {label}
      <select
        data-testid={testId}
        className="mt-1 w-full rounded-lg border border-white/10 bg-slate-800 p-2.5 text-sm text-slate-100 min-h-touch"
        value={`${value.lat},${value.lon}`}
        onChange={(e) => {
          const [lat, lon] = e.target.value.split(",").map(Number);
          const hit = allPlaces().find((p) => p.lat === lat && p.lon === lon);
          if (hit) onChange(hit);
        }}
      >
        {allPlaces().map((p) => (
          <option key={`${p.name}-${p.lat}`} value={`${p.lat},${p.lon}`}>
            {p.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function CorridorCard({
  corridor,
  isCleanest,
  saving,
}: {
  corridor: RouteCorridor;
  isCleanest: boolean;
  saving: number | null;
}): React.JSX.Element {
  // Scale the bars to this corridor's own worst sample so the profile shape is
  // readable instead of squashed under a fixed 350 µg/m³ ceiling that most
  // Delhi days never reach.
  const axisCeiling = Math.max(
    60,
    Math.ceil(Math.max(corridor.peak_pm25, ...corridor.samples.map((x) => x.pm25_mid ?? 0)) / 20) * 20,
  );

  return (
    <article
      data-testid={`corridor-${corridor.rank}`}
      className={`rounded-xl border p-4 ${
        isCleanest
          ? "border-emerald-500/50 bg-emerald-500/5"
          : "border-white/10 bg-slate-900/50"
      }`}
    >
      <header className="mb-3 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
          <span
            className={`grid h-5 w-5 place-items-center rounded-full text-[11px] font-bold ${
              isCleanest ? "bg-emerald-500 text-night-900" : "bg-slate-700 text-slate-200"
            }`}
          >
            {corridor.rank}
          </span>
          {isCleanest ? "Cleanest right now" : "Alternative"}
          {corridor.kind === "straight-line" && (
            <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] text-amber-300">
              not a real road
            </span>
          )}
        </h3>
        {saving !== null && saving > 0 && (
          <span className="shrink-0 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-medium text-emerald-300">
            −{saving.toFixed(1)} µg/m³
          </span>
        )}
      </header>

      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Average" value={corridor.mean_pm25.toFixed(0)} unit="µg/m³" colour={bandColour(corridor.mean_pm25)} />
        <Stat label="Worst point" value={corridor.peak_pm25.toFixed(0)} unit="µg/m³" colour={bandColour(corridor.peak_pm25)} />
        <Stat label="Distance" value={corridor.distance_km.toFixed(1)} unit="km" />
        <Stat label="Driving" value={corridor.duration_min.toFixed(0)} unit="min" />
      </div>

      {corridor.dose_index !== null && (
        <p className="mb-3 text-[11px] leading-relaxed text-slate-400">
          Exposure index {corridor.dose_index.toFixed(0)} = average concentration ×
          time in the vehicle. A cleaner but much longer drive can still be the
          worse choice.
        </p>
      )}

      <div>
        <div className="mb-1 flex items-baseline justify-between">
          <p className="text-[10px] uppercase tracking-wide text-slate-500">
            PM2.5 along the way
          </p>
          <p className="text-[10px] text-slate-500" data-testid={`axis-${corridor.rank}`}>
            {axisCeiling.toFixed(0)} µg/m³ scale
          </p>
        </div>
        <div
          className="flex h-10 items-end gap-[2px]"
          role="img"
          aria-label={`PM2.5 profile along corridor ${corridor.rank}: mean ${corridor.mean_pm25.toFixed(0)}, peak ${corridor.peak_pm25.toFixed(0)} micrograms per cubic metre`}
          data-testid={`profile-${corridor.rank}`}
        >
          {corridor.samples.map((s, i) => {
            const v = s.pm25_mid ?? 0;
            const pct = Math.max(6, Math.min(100, (v / axisCeiling) * 100));
            return (
              <div
                key={`${s.lat}-${s.lon}-${i}`}
                title={`${v.toFixed(0)} µg/m³ · ${s.category ?? "n/a"}`}
                className="flex-1 rounded-t"
                style={{ height: `${pct}%`, background: bandColour(v) }}
              />
            );
          })}
        </div>
        <div className="mt-1 flex justify-between text-[9px] text-slate-500">
          <span>start</span>
          <span data-testid={`worst-segment-${corridor.rank}`}>
            worst stretch {corridor.peak_pm25.toFixed(0)} µg/m³
          </span>
          <span>end</span>
        </div>
      </div>
    </article>
  );
}

function Stat({
  label,
  value,
  unit,
  colour,
}: {
  label: string;
  value: string;
  unit: string;
  colour?: string;
}): React.JSX.Element {
  return (
    <div className="rounded-lg bg-slate-800/60 px-2.5 py-2">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-0.5 font-mono text-base" style={{ color: colour ?? "#e2e8f0" }}>
        {value}
        <span className="ml-0.5 text-[10px] text-slate-500">{unit}</span>
      </div>
    </div>
  );
}

/**
 * "Which way should I go?" - the product's fourth pillar.
 *
 * Routes come from the real road network, PM2.5 is our own estimate sampled
 * along each one, and the ranking is by exposure, not by the router's
 * shortest-first order: the whole point is that the quick way is not always the
 * clean way.
 */
export function RoutesCompare(): React.JSX.Element {
  const { t } = useTranslation();
  const places = useMemo(() => allPlaces(), []);
  const [from, setFrom] = useState<Place>(places.find((p) => p.name === "Connaught Place") ?? places[0]!);
  const [to, setTo] = useState<Place>(places.find((p) => p.name === "Rohini") ?? places[1]!);
  const [swapped, setSwapped] = useState(false);

  // These objects go into the React Query key, so they must be referentially
  // stable: fresh object literals on every render make the key change, which
  // makes the query refetch forever. Each refetch costs a routing + profiling
  // round trip, so the screen never settles.
  const fromEndpoint = useMemo(
    () => ({ lat: from.lat, lon: from.lon, name: from.name }),
    [from],
  );
  const toEndpoint = useMemo(() => ({ lat: to.lat, lon: to.lon, name: to.name }), [to]);
  const result = useRouteCompare(fromEndpoint, toEndpoint);

  function swap(): void {
    setFrom(to);
    setTo(from);
    setSwapped((v) => !v);
  }

  const corridors: RouteCorridor[] = useMemo(() => {
    if (!result.data) return [];
    // the API ranks them; re-order the two it returns for the list
    // Prefer the full ranked list; fall back to the two extremes when the
    // response predates it.
    if (result.data.corridors?.length) return result.data.corridors;
    return [result.data.cleanest, result.data.worst].filter(
      (c, i, arr) => arr.findIndex((x) => x.rank === c.rank) === i,
    );
  }, [result.data]);

  return (
    <div className="mx-auto max-w-6xl p-4">
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-100">{t("routes.title")}</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Real roads, our own PM2.5 estimate sampled along each one. Ranked by
            exposure, not by distance.
          </p>
        </div>
        <button
          type="button"
          onClick={swap}
          data-testid="swap-endpoints"
          className="rounded-lg border border-white/10 bg-slate-800 px-3 py-2 text-sm text-slate-200 min-h-touch hover:bg-slate-700"
        >
          Swap start and end
        </button>
      </header>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <PlaceSelect label="From" value={from} onChange={setFrom} testId="route-from" />
        <PlaceSelect label="To" value={to} onChange={setTo} testId="route-to" />
      </div>

      {result.isPending && <PendingCard />}

      {result.error != null && (
        <div
          role="alert"
          data-testid="routes-error"
          className="rounded-xl border border-red-500/40 bg-red-950/40 p-4 text-sm text-red-300"
        >
          {result.error instanceof Error ? result.error.message : "Route comparison failed."}
        </div>
      )}

      {result.data && (
        <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
          {/* A definite height, not just min-height: the map wrapper resolves
              `h-full` against this box, and with only min-height that resolved
              against an auto height and the canvas collapsed to a sliver. */}
          <div className="order-2 h-[22rem] lg:h-[30rem]">
            <RouteMap
              corridors={corridors}
              origin={result.data.origin}
              destination={result.data.destination}
            />
          </div>

          <div className="order-1 space-y-3 lg:order-2">
            <p
              data-testid="routes-summary"
              className="rounded-xl border border-white/10 bg-slate-900/50 p-3 text-sm text-slate-300"
            >
              <strong className="text-slate-100">
                {from.name} → {to.name}
              </strong>
              : {result.data.corridor_count} real{" "}
              {result.data.corridor_count === 1 ? "route" : "routes"}.
              {result.data.mean_pm25_saving > 0
                ? ` Taking the cleaner one avoids an average of ${result.data.mean_pm25_saving.toFixed(1)} µg/m³.`
                : " They are within noise of each other."}
              {swapped ? null : null}
            </p>

            {corridors.map((c) => (
              <CorridorCard
                key={c.rank}
                corridor={c}
                isCleanest={c.rank === 1}
                saving={
                  c.rank === 1
                    ? result.data!.worst.mean_pm25 - result.data!.cleanest.mean_pm25
                    : null
                }
              />
            ))}

            <p className="rounded-xl border border-white/10 bg-slate-900/40 p-3 text-[11px] leading-relaxed text-slate-400">
              {result.data.note} {result.data.honesty_note}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default RoutesCompare;

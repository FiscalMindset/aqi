import { useState } from "react";
import type { FeatureContribution } from "../../lib/api";

/** Human labels for the raw feature names. Unknown names fall through as-is. */
const LABELS: Record<string, { label: string; help: string }> = {
  station_lag24: {
    label: "Nearest station, 24 h ago",
    help: "Yesterday's value at the closest official station. Stagnant air keeps yesterday's level.",
  },
  station_rolling6: {
    label: "Nearest station, 6 h average",
    help: "Smoothed recent history; tells the model whether pollution is building or clearing.",
  },
  hour_sin: { label: "Time of day (sin)", help: "Traffic and boundary-layer cycle across the day." },
  hour_cos: { label: "Time of day (cos)", help: "Second harmonic of the daily cycle." },
  month_sin: { label: "Month (sin)", help: "Seasonal heating and mixing-height cycle." },
  month_cos: { label: "Month (cos)", help: "Second harmonic of the seasonal cycle." },
  wind_speed: { label: "Wind speed", help: "Stronger wind dilutes and carries pollution away." },
  wind_gust: { label: "Wind gusts", help: "Ventilation: gusts flush particles out of the street canyon." },
  wind_dir_sin: { label: "Wind direction (sin)", help: "Which way the wind blows, relative to the sources." },
  wind_dir_cos: { label: "Wind direction (cos)", help: "Second harmonic of wind direction." },
  temp_c: { label: "Temperature", help: "Warm air mixes less near the surface." },
  rh: { label: "Humidity", help: "Humid air holds more particulate." },
  precip: { label: "Rainfall", help: "Rain washes particles out." },
  landfill_dist_km: { label: "Distance to nearest landfill", help: "How close the nearest waste site is." },
  landfill_count_5km: { label: "Landfills within 5 km", help: "Density of waste sites around the point." },
  industrial_dist_km: { label: "Distance to nearest industry", help: "How close the nearest industrial unit is." },
  industrial_count_5km: { label: "Industries within 5 km", help: "Density of industrial units around the point." },
  construction_dist_km: { label: "Distance to construction", help: "How close the nearest active site is." },
  construction_count_5km: { label: "Construction sites within 5 km", help: "Density of construction around the point." },
  junction_dist_km: { label: "Distance to nearest junction", help: "How close the nearest major road junction is." },
  junction_count_5km: { label: "Junctions within 5 km", help: "Road density: traffic-related emissions." },
};

function label(name: string): { label: string; help: string } {
  return LABELS[name] ?? { label: name.replace(/_/g, " "), help: "" };
}

function formatValue(value: number, unit: string): string {
  if (unit === "dimensionless") return value.toFixed(2);
  if (unit === "index") return String(Math.round(value));
  return `${value.toFixed(1)} ${unit}`;
}

/**
 * "Which parameters produced this number?"
 *
 * Each bar is an occlusion result: the model was re-run with that one parameter
 * set to a typical value while everything else stayed put, and the bar is how
 * far the estimate moved. It is an association in ug/m3, not a causal claim.
 */
export function FeatureBreakdown({
  features,
  anchor,
  adjustment,
  finalValue,
}: {
  features: FeatureContribution[];
  anchor: number | null;
  adjustment: number | null;
  finalValue: number;
}): React.JSX.Element | null {
  const [showAll, setShowAll] = useState(false);
  if (features.length === 0) return null;

  const shown = showAll ? features : features.slice(0, 6);
  const max = Math.max(...features.map((f) => f.absolute_effect_ugm3), 1);
  const strongest = features.filter((f) => f.absolute_effect_ugm3 >= 0.5);
  const top = strongest[0];

  return (
    <section
      data-testid="feature-breakdown"
      className="rounded-xl border border-slate-700/70 bg-slate-900/60 p-4"
    >
      <header className="mb-1 flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-100">
          The inputs used for this exact spot
        </h3>
        <span className="text-[11px] text-slate-400">
          {features.length} parameters used
        </span>
      </header>
      <p className="mb-3 text-[11px] leading-relaxed text-slate-400">
        These are the values the model read <em>for the point you selected</em> —
        the wind, the time of day, the distance to each kind of source and the
        recent station history. Each bar is how much the estimate would change
        if that one input were typical for Delhi instead. Associations in µg/m³,
        not causal claims.
      </p>

      {anchor !== null && (
        <div className="mb-3 flex flex-wrap items-baseline gap-x-2 gap-y-1 rounded-lg bg-slate-800/60 px-3 py-2 text-xs">
          <span className="text-slate-400">Nearest station, 1 h ago</span>
          <span className="font-mono text-slate-200">{anchor.toFixed(0)}</span>
          {adjustment !== null && (
            <>
              <span className="text-slate-500">+</span>
              <span
                className={`font-mono ${adjustment >= 0 ? "text-amber-300" : "text-sky-300"}`}
              >
                {adjustment >= 0 ? "+" : ""}
                {adjustment.toFixed(1)} model
              </span>
            </>
          )}
          <span className="text-slate-500">=</span>
          <span className="font-mono font-semibold text-slate-100">
            {finalValue.toFixed(0)} µg/m³
          </span>
        </div>
      )}

      <ul className="space-y-2">
        {shown.map((f) => {
          const meta = label(f.name);
          const width = (f.absolute_effect_ugm3 / max) * 100;
          const up = f.contribution_ugm3 >= 0;
          return (
            <li key={f.name}>
              <div className="flex items-baseline justify-between gap-2 text-[11px]">
                <span
                  className="truncate text-slate-200"
                  title={meta.help || meta.label}
                >
                  {meta.label}
                </span>
                <span
                  className={`shrink-0 font-mono tabular-nums ${
                    up ? "text-amber-300" : "text-sky-300"
                  }`}
                >
                  {up ? "+" : ""}
                  {f.contribution_ugm3.toFixed(1)}
                </span>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
                  <div
                    className={`h-full rounded-full ${
                      up ? "bg-amber-400/80" : "bg-sky-400/80"
                    }`}
                    style={{ width: `${Math.max(width, 1)}%` }}
                  />
                </div>
                <span className="w-24 shrink-0 text-right font-mono text-[10px] text-slate-500">
                  {formatValue(f.value, f.unit)}
                </span>
              </div>
            </li>
          );
        })}
      </ul>

      {features.length > 6 && (
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          className="mt-3 text-[11px] font-medium text-emerald-300 hover:text-emerald-200"
        >
          {showAll ? "Show fewer" : `Show all ${features.length} parameters`}
        </button>
      )}

      {top && (
        <p className="mt-3 border-t border-slate-800 pt-2 text-[11px] leading-relaxed text-slate-400">
          Dominant input:{" "}
          <span className="text-slate-200">{label(top.name).label}</span>
          {label(top.name).help ? ` — ${label(top.name).help}` : ""}
        </p>
      )}
    </section>
  );
}
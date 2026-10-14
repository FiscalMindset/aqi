/**
 * What the model was trained on.
 *
 * Counts here are read from the training snapshot in the image at request
 * time, not typed into a page. If the model is retrained, these numbers move
 * with it - which is the only reason to show them at all. A hand-written
 * "trained on 500k observations" goes stale silently.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg bg-slate-800/60 p-2.5">
      <p className="text-[10px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 font-mono text-base">{value}</p>
      {note && <p className="mt-0.5 text-[10px] text-slate-500">{note}</p>}
    </div>
  );
}

export function TrainingDataPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ["training-data"],
    queryFn: () => api.trainingData(),
    staleTime: 60 * 60_000,
  });

  if (isLoading) {
    return (
      <section className="rounded-xl border border-white/10 bg-slate-900/40 p-3">
        <h2 className="text-sm font-semibold">Training data</h2>
        <p className="mt-1 text-xs text-slate-400">Reading the snapshot…</p>
      </section>
    );
  }
  if (!data) return null;

  if (!data.available) {
    return (
      <section className="rounded-xl border border-white/10 bg-slate-900/40 p-3">
        <h2 className="text-sm font-semibold">Training data</h2>
        <p className="mt-1 text-xs text-slate-400">{data.reason}</p>
      </section>
    );
  }

  const m = data.metrics ?? {};
  const fmt = (v: unknown, d = 0) =>
    typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: d }) : "—";

  return (
    <details
      className="rounded-xl border border-white/10 bg-slate-900/40 p-3"
      data-testid="training-data-panel"
    >
      <summary className="cursor-pointer text-sm font-semibold marker:text-slate-500">
        What this model was trained on
      </summary>

      <div className="mt-3 space-y-3">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat
            label="Station readings"
            value={fmt(data.station_observations)}
            note={`${data.stations} monitoring stations`}
          />
          <Stat
            label="Weather observations"
            value={fmt(data.weather_observations)}
            note="matched to the same hours"
          />
          <Stat
            label="Coverage"
            value={`${data.first_observation} → ${data.last_observation}`}
            note="hourly PM2.5"
          />
          <Stat
            label="Features"
            value={String(data.feature_count)}
            note="inputs per prediction"
          />
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Observed min" value={`${data.observed_min_ugm3.toFixed(0)} µg/m³`} />
          <Stat label="Observed mean" value={`${data.observed_mean_ugm3.toFixed(1)} µg/m³`} />
          <Stat label="Observed max" value={`${data.observed_max_ugm3.toFixed(0)} µg/m³`} />
          <Stat
            label="Busiest station"
            value={fmt(data.busiest_station_rows)}
            note={`median ${fmt(data.median_station_rows)}`}
          />
        </div>

        <details className="rounded-lg bg-slate-800/40 p-2.5">
          <summary className="cursor-pointer text-xs font-medium marker:text-slate-500">
            The {data.feature_count} inputs
          </summary>
          <ul className="mt-2 flex flex-wrap gap-1">
            {data.features.map((f: string) => (
              <li
                key={f}
                className="rounded bg-slate-900/70 px-1.5 py-0.5 font-mono text-[10px] text-slate-300"
              >
                {f}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[10px] text-slate-500">
            Time-of-day and calendar terms are encoded as sin/cos so midnight and
            noon are neighbours rather than opposites. The station lag terms
            anchor the prediction to what a real monitor recently reported.
          </p>
        </details>

        {data.sources && Object.keys(data.sources).length > 0 && (
          <div className="rounded-lg bg-slate-800/40 p-2.5 text-[11px] text-slate-400">
            <p className="mb-1 font-medium text-slate-300">Provenance</p>
            {Object.entries(data.sources).map(([k, v]) => (
              <p key={k}>
                <span className="font-mono">{k}</span>: {String(v)}
              </p>
            ))}
          </div>
        )}

        <p className="text-[11px] text-slate-500">
          Evaluation run {String(m.version ?? "—")} ·{" "}
          {fmt(m.n_rows)} labelled rows · winner{" "}
          <span className="font-mono">{String(m.winner ?? "—")}</span>
        </p>
      </div>
    </details>
  );
}

export default TrainingDataPanel;
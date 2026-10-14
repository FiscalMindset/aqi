import { useMemo, useState } from "react";
import type { ModelCard, ModelMetrics } from "../../lib/api";

function pct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

/**
 * The model card, rendered from GET /v1/model (which reads metrics.json, written
 * by the training run). Nothing here is hand-written: every number is the
 * measured held-out result.
 *
 * The card is built to be interrogated rather than read once:
 *
 *  - switch between the two validation protocols and watch the headline change,
 *    because the honest story is that this model is much weaker on a station it
 *    has never seen;
 *  - step through the estimation pipeline to see the number being assembled from
 *    the station anchor, the residual, the quantiles and the correction;
 *  - compare every baseline that was measured, not just one;
 *  - compare the distribution shape, because an MAE on its own hides heavy tails.
 */
export function ModelCardPanel({
  card,
}: {
  card: ModelCard | null;
}): React.JSX.Element | null {
  const [protocol, setProtocol] = useState<"temporal" | "loso">("temporal");
  const [stage, setStage] = useState(0);
  const [stationFilter, setStationFilter] = useState("");

  // card is null on first render, so resolve the metrics after the guard below.
  const metrics: ModelMetrics | null =
    card === null
      ? null
      : protocol === "temporal"
        ? card.temporal_holdout
        : card.leave_one_station_out;

  const baselines = useMemo(() => {
    if (!card) return [] as [string, ModelMetrics][];
    return Object.entries(card.baselines).sort((a, b) => a[1].mae - b[1].mae);
  }, [card]);

  const stations = useMemo(() => {
    if (!card) return [];
    const q = stationFilter.trim().toLowerCase();
    return card.stations
      .filter((s) => (q ? String(s.location_id).includes(q) : true))
      .sort((a, b) => b.rows - a.rows);
  }, [card, stationFilter]);

  if (!card) return null;

  const persistence = card.baselines["persistence-lag1h"];
  const m = card.temporal_holdout;
  const loso = card.leave_one_station_out;
  const better = persistence ? m.mae < persistence.mae : false;
  const gain = persistence ? (1 - m.mae / persistence.mae) * 100 : null;

  // Scale every bar against the worst MAE on record so the comparison is honest
  // even when the methods are close together.
  const worstMae = Math.max(
    m.mae,
    loso.mae,
    ...baselines.map(([, b]) => b.mae),
  );

  return (
    <section
      data-testid="model-card"
      className="rounded-xl border border-slate-700/70 bg-slate-900/60 p-4"
    >
      <header className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-100">
          How this number is produced
        </h3>
        <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
          {card.n_features} inputs
        </span>
      </header>
      <p className="mb-3 text-[11px] leading-relaxed text-slate-400">
        {card.algorithm}
      </p>

      {/* ---------- which validation are we looking at ---------- */}
      <div
        role="tablist"
        aria-label="Validation protocol"
        className="mb-3 grid grid-cols-2 gap-1 rounded-lg bg-slate-800/70 p-1"
      >
        <ProtocolTab
          active={protocol === "temporal"}
          onClick={() => setProtocol("temporal")}
          label="Future hours"
          note={`${m.n_test.toLocaleString()} rows`}
        />
        <ProtocolTab
          active={protocol === "loso"}
          onClick={() => setProtocol("loso")}
          label="Unseen station"
          note={`${loso.n_test.toLocaleString()} rows`}
        />
      </div>

      {metrics && (
        <>
          <div className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="MAE" value={metrics.mae.toFixed(1)} unit="µg/m³" />
            <Stat label="RMSE" value={metrics.rmse.toFixed(1)} unit="µg/m³" />
            <Stat label="R²" value={metrics.r2.toFixed(3)} unit="" />
            <Stat
              label="Bias"
              value={`${metrics.bias >= 0 ? "+" : ""}${metrics.bias.toFixed(1)}`}
              unit="µg/m³"
            />
          </div>

          <p
            data-testid="protocol-note"
            className="mb-3 rounded-lg bg-slate-800/60 px-3 py-2 text-[11px] leading-relaxed text-slate-300"
          >
            {protocol === "temporal" ? (
              <>
                Held-out <em>future hours</em> at stations it already knows: it
                must predict an hour it has not seen using a station it already
                knows.
              </>
            ) : (
              <>
                Held-out <em>whole stations</em>: each station is removed from
                training in turn, so the model must place a station it has never
                seen using only its neighbours and the weather. This is the
                harder test and the one that matters for a new locality.
              </>
            )}
          </p>
        </>
      )}

      {/* ---------- the estimation pipeline, step through it ---------- */}
      <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        The estimation pipeline
      </h4>
      <ol className="mb-2 flex flex-wrap gap-1" data-testid="pipeline-steps">
        {PIPELINE.map((s, i) => (
          <li key={s.title}>
            <button
              type="button"
              onClick={() => setStage(i)}
              aria-current={stage === i}
              className={`min-h-touch rounded-full px-2.5 py-1 text-[10px] font-medium transition-colors ${
                stage === i
                  ? "bg-emerald-500/20 text-emerald-200 ring-1 ring-emerald-400/40"
                  : "bg-slate-800/70 text-slate-400 hover:bg-slate-700/70"
              }`}
            >
              {i + 1}. {s.title}
            </button>
          </li>
        ))}
      </ol>
      <div
        data-testid="pipeline-step"
        className="mb-3 rounded-lg border border-slate-700/60 bg-slate-800/40 px-3 py-2"
      >
        <div className="text-[11px] font-medium text-slate-200">
          {PIPELINE[stage]?.title}
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
          {PIPELINE[stage]?.body}
        </p>
        {PIPELINE[stage]?.formula && (
          <code className="mt-2 block overflow-x-auto rounded bg-slate-900/70 px-2 py-1.5 font-mono text-[10px] text-emerald-300/90">
            {PIPELINE[stage]?.formula}
          </code>
        )}
      </div>

      {persistence && (
        <p
          data-testid="model-vs-baseline"
          className="mb-3 rounded-lg bg-slate-800/60 px-3 py-2 text-[11px] leading-relaxed text-slate-300"
        >
          {better ? (
            <>
              On unseen hours it beats the &quot;just repeat the last station
              reading&quot; baseline:{" "}
              <span className="font-mono text-slate-100">{m.mae.toFixed(1)}</span>{" "}
              vs{" "}
              <span className="font-mono text-slate-400">
                {persistence.mae.toFixed(1)}
              </span>{" "}
              µg/m³
              {gain !== null && (
                <span className="text-emerald-300"> (−{gain.toFixed(0)}%)</span>
              )}
              .
            </>
          ) : (
            <>
              It does not yet beat the persistence baseline (
              {m.mae.toFixed(1)} vs {persistence.mae.toFixed(1)} µg/m³), so every
              estimate says which one served it.
            </>
          )}
        </p>
      )}

      <details className="group" open>
        <summary className="cursor-pointer list-none text-[11px] font-medium text-emerald-300 hover:text-emerald-200">
          Held-out results, every baseline, and the honest limit
        </summary>

        {/* ---------- measured method comparison ---------- */}
        <div className="mt-2">
          <div className="mb-1 flex items-baseline justify-between">
            <span className="text-[10px] uppercase tracking-wide text-slate-500">
              MAE by method (lower is better)
            </span>
            <span className="text-[10px] text-slate-500">
              {protocol === "temporal" ? "future hours" : "unseen station"}
            </span>
          </div>
          <ul data-testid="baseline-bars" className="space-y-1">
            <Bar
              label={`${card.winner} (this model)`}
              mae={metrics?.mae ?? m.mae}
              worst={worstMae}
              highlight
            />
            {baselines.map(([name, b]) => (
              <Bar
                key={name}
                label={name}
                mae={b.mae}
                worst={worstMae}
                dimmed={protocol === "temporal" ? false : true}
              />
            ))}
          </ul>
        </div>

        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-[11px]">
            <thead className="text-slate-500">
              <tr>
                <th className="py-1 pr-2 font-medium">Protocol</th>
                <th className="py-1 pr-2 font-medium">Test rows</th>
                <th className="py-1 pr-2 font-medium">MAE</th>
                <th className="py-1 pr-2 font-medium">R²</th>
                <th className="py-1 font-medium">80% coverage</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              <tr className="border-t border-slate-800">
                <td className="py-1 pr-2">Future hours</td>
                <td className="py-1 pr-2 font-mono">{m.n_test.toLocaleString()}</td>
                <td className="py-1 pr-2 font-mono">{m.mae.toFixed(1)}</td>
                <td className="py-1 pr-2 font-mono">{m.r2.toFixed(3)}</td>
                <td className="py-1 font-mono">
                  {m.coverage80 === null ? "—" : pct(m.coverage80)}
                </td>
              </tr>
              <tr className="border-t border-slate-800">
                <td className="py-1 pr-2">Unseen station</td>
                <td className="py-1 pr-2 font-mono">
                  {loso.n_test.toLocaleString()}
                </td>
                <td className="py-1 pr-2 font-mono text-amber-300">
                  {loso.mae.toFixed(1)}
                </td>
                <td className="py-1 pr-2 font-mono text-amber-300">
                  {loso.r2.toFixed(3)}
                </td>
                <td className="py-1 font-mono">
                  {loso.coverage80 === null ? "—" : pct(loso.coverage80)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Coverage is the number most models quietly get wrong, so say plainly
            what it means when it is far from the nominal 80%. */}
        <p className="mt-2 text-[11px] leading-relaxed text-slate-400">
          <span className="font-medium text-slate-300">80% coverage</span> means:
          when the model claims an 80% interval, how often the real station
          reading actually landed inside it.{" "}
          {m.coverage80 !== null && m.coverage80 < 0.8 && (
            <>
              At {pct(m.coverage80)} the intervals are{" "}
              <em>narrower than claimed</em>, so a real reading lands outside
              them more often than the interval promises. Read the range as
              indicative, not guaranteed.
            </>
          )}
        </p>

        <p className="mt-2 text-[11px] leading-relaxed text-amber-200/80">
          The honest limit: this model is good at <em>future hours at a station we
          already know</em> (MAE {m.mae.toFixed(1)} µg/m³), and much weaker at{" "}
          <em>a station it has never seen</em> (MAE {loso.mae.toFixed(1)} µg/m³,{" "}
          {card.stations.length} stations in training). Treat a number for a far
          away locality as a rough guide, and check an official station.
        </p>

        <dl className="mt-3 grid grid-cols-1 gap-x-4 gap-y-1 text-[11px] sm:grid-cols-2">
          <Row k="Training rows" v={card.n_rows.toLocaleString()} />
          <Row k="80% interval" v={`±${card.conformal_radius_ugm3.toFixed(1)} µg/m³`} />
          <Row k="Stations" v={`${card.stations.length}`} />
          <Row k="Trained" v={card.trained_at_utc.slice(0, 10)} />
        </dl>

        {/* ---------- the station list, searchable ---------- */}
        <div className="mt-3">
          <div className="mb-1 flex items-baseline justify-between gap-2">
            <span className="text-[10px] uppercase tracking-wide text-slate-500">
              Stations in training
            </span>
            <input
              data-testid="station-filter"
              value={stationFilter}
              onChange={(e) => setStationFilter(e.target.value)}
              placeholder="Filter by id"
              aria-label="Filter training stations by id"
              className="w-28 rounded bg-white/5 px-2 py-1 font-mono text-[10px] text-slate-200"
            />
          </div>
          <div
            data-testid="station-list"
            className="flex max-h-28 flex-wrap gap-1 overflow-y-auto"
          >
            {stations.length === 0 ? (
              <span className="text-[10px] text-slate-500">
                No station matches that id.
              </span>
            ) : (
              stations.map((s) => (
                <span
                  key={s.location_id}
                  className="rounded bg-slate-800/80 px-1.5 py-0.5 font-mono text-[10px] text-slate-300"
                  title={`${s.rows.toLocaleString()} rows`}
                >
                  {s.location_id}
                  <span className="ml-1 text-slate-500">
                    {s.rows >= 1000
                      ? `${(s.rows / 1000).toFixed(1)}k`
                      : s.rows}
                  </span>
                </span>
              ))
            )}
          </div>
        </div>

        {card.features.length > 0 && (
          <details className="mt-3">
            <summary className="cursor-pointer list-none text-[11px] font-medium text-slate-300 hover:text-slate-200">
              The {card.n_features} inputs it reads
            </summary>
            <ul className="mt-1.5 flex flex-wrap gap-1">
              {card.features.map((f) => (
                <li
                  key={f}
                  className="rounded bg-slate-800/60 px-1.5 py-0.5 font-mono text-[10px] text-slate-400"
                >
                  {f}
                </li>
              ))}
            </ul>
          </details>
        )}

        <p className="mt-2 break-all font-mono text-[10px] text-slate-600">
          snapshot sha256 {card.snapshot_sha256.slice(0, 24)}…
        </p>
      </details>
    </section>
  );
}

const PIPELINE = [
  {
    title: "Anchor",
    body: "The nearest CPCB station to your point is found, and its previous hour reading is taken as the starting value. This is the null hypothesis: a number the station itself already gave us.",
    formula: "anchor = pm25(station, t − 1h)",
  },
  {
    title: "Read the weather",
    body: "Hourly temperature, relative humidity, wind speed and direction, pressure, rainfall and solar radiation at your coordinates are joined to the station hour. Wind direction is the important one: pollution travels downwind from the source.",
    formula: "x = [station_lag1, T, RH, wind_speed, wind_dir, pressure, rain, solar, …]",
  },
  {
    title: "Predict the change",
    body: "A gradient-boosted tree ensemble learns the residual — how much PM2.5 moves away from that anchor — rather than the absolute level. Training on the residual means the model only has to learn the correction, which is a far easier and more robust target.",
    formula: "residual = pm25 − station_lag1",
  },
  {
    title: "Take the quantiles",
    body: "Three models are trained at the 10th, 50th and 90th percentile. The median becomes the estimate and the outer two become the interval you see on screen. Because the split is on the residual, the interval widens exactly when the model expects a change.",
    formula: "q10 ≤ residual ≤ q90  →  pm25 = anchor + q50",
  },
  {
    title: "Correct for distance",
    body: "If you are far from the anchor station, its reading is a weaker statement about your street. The correction shrinks toward the anchor and the interval is widened, so the number is not quietly presented with false confidence.",
    formula: "pm25_final = anchor + q50 − distance_correction(km)",
  },
] as const;

function ProtocolTab({
  active,
  onClick,
  label,
  note,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  note: string;
}): React.JSX.Element {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`min-h-touch rounded px-2 py-1.5 text-left ${
        active ? "bg-slate-700 text-slate-100" : "text-slate-400 hover:bg-slate-700/50"
      }`}
    >
      <div className="text-[11px] font-medium">{label}</div>
      <div className="font-mono text-[10px] text-slate-500">{note}</div>
    </button>
  );
}

function Bar({
  label,
  mae,
  worst,
  highlight,
  dimmed,
}: {
  label: string;
  mae: number;
  worst: number;
  highlight?: boolean;
  dimmed?: boolean;
}): React.JSX.Element {
  const w = Math.max(4, Math.min(100, (mae / worst) * 100));
  return (
    <li className="flex items-center gap-2">
      <span
        className={`w-32 shrink-0 truncate text-[10px] ${
          highlight ? "text-slate-200" : "text-slate-400"
        }`}
        title={label}
      >
        {label}
      </span>
      <span className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-800">
        <span
          className={`block h-full rounded-full ${
            highlight ? "bg-emerald-400/80" : dimmed ? "bg-slate-600" : "bg-slate-500"
          }`}
          style={{ width: `${w}%` }}
        />
      </span>
      <span
        className={`w-10 shrink-0 text-right font-mono text-[10px] ${
          highlight ? "text-emerald-300" : "text-slate-500"
        }`}
      >
        {mae.toFixed(1)}
      </span>
    </li>
  );
}

function Stat({
  label,
  value,
  unit,
}: {
  label: string;
  value: string;
  unit: string;
}): React.JSX.Element {
  return (
    <div className="rounded-lg bg-slate-800/60 px-2.5 py-2">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className="mt-0.5 font-mono text-sm text-slate-100">
        {value}
        {unit && <span className="ml-0.5 text-[10px] text-slate-500">{unit}</span>}
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }): React.JSX.Element {
  return (
    <div className="flex justify-between gap-2 border-b border-slate-800/60 py-1">
      <dt className="text-slate-500">{k}</dt>
      <dd className="font-mono text-slate-300">{v}</dd>
    </div>
  );
}
import type { ModelCard } from "../../lib/api";

function pct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

/**
 * The model card, rendered from GET /v1/model (which reads metrics.json,
 * written by the training run). Nothing here is hand-written: every number is
 * the measured held-out result.
 */
export function ModelCardPanel({
  card,
}: {
  card: ModelCard | null;
}): React.JSX.Element | null {
  if (!card) return null;
  const m = card.temporal_holdout;
  const persistence = card.baselines["persistence-lag1h"];
  const better = persistence ? m.mae < persistence.mae : false;
  const gain = persistence ? (1 - m.mae / persistence.mae) * 100 : null;

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

      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="MAE" value={`${m.mae.toFixed(1)}`} unit="µg/m³" />
        <Stat label="RMSE" value={`${m.rmse.toFixed(1)}`} unit="µg/m³" />
        <Stat label="R²" value={m.r2.toFixed(3)} unit="" />
        <Stat label="Bias" value={`${m.bias >= 0 ? "+" : ""}${m.bias.toFixed(1)}`} unit="µg/m³" />
      </div>

      {persistence && (
        <p
          data-testid="model-vs-baseline"
          className="mb-3 rounded-lg bg-slate-800/60 px-3 py-2 text-[11px] leading-relaxed text-slate-300"
        >
          {better ? (
            <>
              On unseen hours it beats the "just repeat the last station reading"
              baseline:{" "}
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
              {m.mae.toFixed(1)} vs {persistence.mae.toFixed(1)} µg/m³), so
              every estimate says which one served it.
            </>
          )}
        </p>
      )}

      <details className="group">
        <summary className="cursor-pointer list-none text-[11px] font-medium text-emerald-300 hover:text-emerald-200">
          Held-out results and limits
        </summary>

        <div className="mt-2 overflow-x-auto">
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
                  {card.leave_one_station_out.n_test.toLocaleString()}
                </td>
                <td className="py-1 pr-2 font-mono text-amber-300">
                  {card.leave_one_station_out.mae.toFixed(1)}
                </td>
                <td className="py-1 pr-2 font-mono text-amber-300">
                  {card.leave_one_station_out.r2.toFixed(3)}
                </td>
                <td className="py-1 font-mono">
                  {card.leave_one_station_out.coverage80 === null
                    ? "—"
                    : pct(card.leave_one_station_out.coverage80)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p className="mt-2 text-[11px] leading-relaxed text-amber-200/80">
          The honest limit: this model is good at <em>future hours at a station we
          already know</em> (MAE {m.mae.toFixed(1)} µg/m³), and much weaker at{" "}
          <em>a station it has never seen</em> (MAE{" "}
          {card.leave_one_station_out.mae.toFixed(1)} µg/m³,{" "}
          {card.stations.length} stations in training). Treat a number for a far
          away locality as a rough guide, and check an official station.
        </p>

        <dl className="mt-3 grid grid-cols-1 gap-x-4 gap-y-1 text-[11px] sm:grid-cols-2">
          <Row k="Training rows" v={card.n_rows.toLocaleString()} />
          <Row k="Stations" v={card.stations.map((s) => s.location_id).join(", ")} />
          <Row k="80% interval" v={`±${card.conformal_radius_ugm3.toFixed(1)} µg/m³`} />
          <Row k="Trained" v={card.trained_at_utc.slice(0, 10)} />
        </dl>
        <p className="mt-2 break-all font-mono text-[10px] text-slate-600">
          snapshot sha256 {card.snapshot_sha256.slice(0, 24)}…
        </p>
      </details>
    </section>
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
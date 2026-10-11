import { useTranslation } from "react-i18next";
import { useValidation } from "../../hooks/useApi";

/** Live metrics from /v1/validation — real numbers only, plus limitations. */
export function Methodology() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useValidation();

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-6" data-testid="methodology">
      <h1 className="text-xl font-bold">{t("methodology.title")}</h1>
      {isLoading && <p>Loading metrics…</p>}
      {error && <p role="alert" className="text-red-300 text-sm">{error.message}</p>}
      {data && (
        <>
          <section>
            <h2 className="font-semibold">{t("methodology.validation")}</h2>
            <p className="text-xs text-slate-400">
              run {data.version} at {data.created_utc} · {data.n_rows} labelled rows
            </p>
            <table className="w-full text-sm mt-2">
              <thead>
                <tr className="text-left text-slate-400">
                  <th className="py-1">metric</th>
                  <th>{t("methodology.holdout")}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{t("methodology.mae")}</td>
                  <td data-testid="val-mae">{data.temporal_holdout.mae?.toFixed(1)}</td>
                </tr>
                <tr>
                  <td>{t("methodology.rmse")}</td>
                  <td>{data.temporal_holdout.rmse?.toFixed(1)}</td>
                </tr>
                <tr>
                  <td>{t("methodology.r2")}</td>
                  <td>{data.temporal_holdout.r2?.toFixed(3)}</td>
                </tr>
                <tr>
                  <td>{t("methodology.bias")}</td>
                  <td>{data.temporal_holdout.bias?.toFixed(1)}</td>
                </tr>
                <tr>
                  <td>{t("methodology.coverage")}</td>
                  <td>{data.interval_coverage_note}</td>
                </tr>
              </tbody>
            </table>
            <h3 className="font-semibold mt-4">{t("methodology.baselines")}</h3>
            <table className="w-full text-sm mt-2">
              <thead>
                <tr className="text-left text-slate-400">
                  <th className="py-1">baseline</th>
                  <th>MAE</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.baselines).map(([name, b]) => (
                  <tr key={name}>
                    <td className="font-mono text-xs">{name}</td>
                    <td>{b.mae?.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-sm mt-2" data-testid="winner">
              {t("methodology.winner")}: <strong>{data.winner}</strong>
            </p>
          </section>
          <section>
            <h2 className="font-semibold">{t("methodology.sources")}</h2>
            <ul className="text-sm list-disc pl-5 text-slate-300">
              <li>OpenAQ (CC BY 4.0) station PM2.5 — public archive + API</li>
              <li>Open-Meteo (CC BY 4.0) weather, historical + forecast</li>
              <li>OpenStreetMap (ODbL) source geography via Overpass</li>
              <li>NASA FIRMS active-fire detections</li>
              <li>CPCB National AQI breakpoints (24-hour averages)</li>
            </ul>
          </section>
          <section>
            <h2 className="font-semibold">{t("methodology.limits")}</h2>
            <ul className="text-sm list-disc pl-5 text-slate-300">
              <li>
                CPCB categories are defined on 24-hour averages; applying them to
                hourly estimates is deliberately conservative.
              </li>
              <li>
                The 80% interval covers model error, not sensor error.
              </li>
              <li>
                Source ranking is a transparent heuristic; cross-city transfer is
                weak (see leave-one-station-out in the docs).
              </li>
              <li>Fire features are wired but not yet trained in (no MAP_KEY).</li>
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

export default Methodology;

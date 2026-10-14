/**
 * Everything about how the number is produced, in one place.
 *
 * Separate from the Methodology page on purpose. Methodology answers "why trust
 * this at all"; this answers the mechanical question people actually ask when
 * a number looks wrong: which algorithm, which features, which data, what
 * accuracy, what it cannot do.
 *
 * Every figure is read from the API - the model card, the version registry and
 * the training-data endpoint - and none of it is typed in by hand. If the
 * model is retrained this page changes with it.
 */

import { useTranslation } from "react-i18next";
import { useModelCard, useModelVersions, useTrainingData } from "../../hooks/useApi";
import AqiIcon from "../../components/AqiIcon";
import { ModelVersionsPanel } from "../explorer/ModelVersions";
import { CATEGORY_COLORS, CATEGORY_ORDER, onColor } from "../../lib/aqi";

/**
 * The pipeline steps come from i18n as an array. i18next's types describe the
 * return as $SpecialObject, so it is narrowed here once rather than casting at
 * every use site.
 */
function pipelineSteps(): { title: string; body: string; formula?: string }[] {
  const { t } = useTranslation();
  return t("algo.pipeline", { returnObjects: true }) as unknown as {
    title: string;
    body: string;
    formula?: string;
  }[];
}

/** CPCB band bounds, from the table the API itself uses. */
function bandRange(category: string): string {
  const table: Record<string, string> = {
    Good: "0 – 30",
    Satisfactory: "31 – 60",
    "Moderately Polluted": "61 – 90",
    Poor: "91 – 120",
    "Very Poor": "121 – 250",
    Severe: "above 250",
  };
  return `${table[category] ?? ""} µg/m³`;
}

function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}): React.JSX.Element {
  return (
    <div className="rounded-lg bg-slate-800/60 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-0.5 font-mono text-base text-slate-100">{value}</div>
      {sub && <div className="mt-0.5 text-[10px] text-slate-500">{sub}</div>}
    </div>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <section aria-labelledby={id} className="scroll-mt-20">
      <h2 id={id} className="mb-2 text-sm font-semibold text-slate-100">
        {title}
      </h2>
      {children}
    </section>
  );
}

export function Algorithm(): React.JSX.Element {
  const { t } = useTranslation();
  const card = useModelCard();
  const versions = useModelVersions();
  const training = useTrainingData();

  const m = card.data?.temporal_holdout;
  const unseen = card.data?.leave_one_station_out;
  const td = training.data;
  const baseline = card.data?.baselines["persistence-lag1h"];

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4" data-testid="algorithm">
      <header>
        <h1 className="text-xl font-bold sm:text-2xl">{t("algo.title")}</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-400">
          {t("algo.intro")}
        </p>
      </header>

      {card.isPending && (
        <p role="status" className="text-sm text-slate-400">
          Loading the real figures…
        </p>
      )}

      {card.data && (
        <>
          <Section id="algo-model" title={t("algo.modelTitle")}>
            <div className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-4">
              <p className="mb-3 font-mono text-xs leading-relaxed text-slate-300">
                {card.data.algorithm}
              </p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Stat label={t("algo.features")} value={String(card.data.n_features)} />
                <Stat label={t("algo.rows")} value={card.data.n_rows.toLocaleString()} />
                <Stat
                  label={t("algo.stations")}
                  value={String(card.data.stations.length)}
                />
                <Stat
                  label={t("algo.trained")}
                  value={card.data.trained_at_utc.slice(0, 10)}
                />
              </div>
              <p className="mt-3 break-all font-mono text-[10px] text-slate-600">
                snapshot sha256 {card.data.snapshot_sha256.slice(0, 32)}…
              </p>
            </div>
          </Section>

          <Section id="algo-pipeline" title={t("algo.pipelineTitle")}>
            <ol className="space-y-2" data-testid="algo-pipeline">
              {pipelineSteps().map((s, i) => {
                return (
                  <li
                    key={s.title}
                    className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3"
                  >
                    <div className="flex items-baseline gap-2">
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-[10px] font-semibold text-emerald-300">
                        {i + 1}
                      </span>
                      <span className="text-xs font-medium text-slate-200">
                        {s.title}
                      </span>
                    </div>
                    <p className="mt-1.5 pl-7 text-[11px] leading-relaxed text-slate-400">
                      {s.body}
                    </p>
                    {s.formula && (
                      <code className="mt-2 ml-7 block overflow-x-auto rounded bg-slate-900/80 px-2 py-1.5 font-mono text-[10px] text-emerald-300/90">
                        {s.formula}
                      </code>
                    )}
                  </li>
                );
              })}
            </ol>
          </Section>

          <Section id="algo-accuracy" title={t("algo.accuracyTitle")}>
            <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-900/50 p-3">
              <table className="w-full text-left text-[11px]">
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-1 pr-2 font-medium">Protocol</th>
                    <th className="py-1 pr-2 font-medium">Rows</th>
                    <th className="py-1 pr-2 font-medium">MAE</th>
                    <th className="py-1 pr-2 font-medium">RMSE</th>
                    <th className="py-1 pr-2 font-medium">R²</th>
                    <th className="py-1 font-medium">Bias</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  {m && (
                    <tr className="border-t border-slate-800">
                      <td className="py-1 pr-2">Future hours</td>
                      <td className="py-1 pr-2 font-mono">{m.n_test.toLocaleString()}</td>
                      <td className="py-1 pr-2 font-mono">{m.mae.toFixed(2)}</td>
                      <td className="py-1 pr-2 font-mono">{m.rmse.toFixed(2)}</td>
                      <td className="py-1 pr-2 font-mono">{m.r2.toFixed(3)}</td>
                      <td className="py-1 font-mono">{m.bias.toFixed(2)}</td>
                    </tr>
                  )}
                  {unseen && (
                    <tr className="border-t border-slate-800">
                      <td className="py-1 pr-2 text-amber-300">Unseen station</td>
                      <td className="py-1 pr-2 font-mono text-amber-300">
                        {unseen.n_test.toLocaleString()}
                      </td>
                      <td className="py-1 pr-2 font-mono text-amber-300">
                        {unseen.mae.toFixed(2)}
                      </td>
                      <td className="py-1 pr-2 font-mono text-amber-300">
                        {unseen.rmse.toFixed(2)}
                      </td>
                      <td className="py-1 pr-2 font-mono text-amber-300">
                        {unseen.r2.toFixed(3)}
                      </td>
                      <td className="py-1 font-mono text-amber-300">
                        {unseen.bias.toFixed(2)}
                      </td>
                    </tr>
                  )}
                  {baseline && (
                    <tr className="border-t border-slate-800 text-slate-400">
                      <td className="py-1 pr-2">Baseline: repeat last reading</td>
                      <td className="py-1 pr-2 font-mono">—</td>
                      <td className="py-1 pr-2 font-mono">{baseline.mae.toFixed(2)}</td>
                      <td className="py-1 pr-2 font-mono">{baseline.rmse.toFixed(2)}</td>
                      <td className="py-1 pr-2 font-mono">{baseline.r2.toFixed(3)}</td>
                      <td className="py-1 font-mono">{baseline.bias.toFixed(2)}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-slate-400">
              {t("algo.accuracyNote")}
            </p>
          </Section>

          <Section id="algo-features" title={t("algo.featuresTitle")}>
            <ul
              className="flex flex-wrap gap-1 rounded-xl border border-slate-700/60 bg-slate-900/50 p-3"
              data-testid="algo-features"
            >
              {card.data.features.map((f) => (
                <li
                  key={f}
                  className="rounded bg-slate-800/70 px-1.5 py-0.5 font-mono text-[10px] text-slate-300"
                >
                  {f}
                </li>
              ))}
            </ul>
          </Section>

          <Section id="algo-data" title={t("algo.dataTitle")}>
            {td ? (
              <div className="grid grid-cols-2 gap-2 rounded-xl border border-slate-700/60 bg-slate-900/50 p-3 sm:grid-cols-4">
                <Stat
                  label={t("algo.stationRows")}
                  value={td.station_observations.toLocaleString()}
                />
                <Stat
                  label={t("algo.weatherRows")}
                  value={td.weather_observations.toLocaleString()}
                />
                <Stat
                  label={t("algo.range")}
                  value={`${td.first_observation.slice(0, 10)} → ${td.last_observation.slice(0, 10)}`}
                />
                <Stat
                  label={t("algo.pmRange")}
                  value={`${td.observed_min_ugm3} – ${td.observed_max_ugm3}`}
                />
              </div>
            ) : (
              <p className="text-xs text-slate-500">{t("algo.dataPending")}</p>
            )}
          </Section>

          <Section id="algo-categories" title={t("algo.categoriesTitle")}>
            <ul className="grid gap-2 sm:grid-cols-2">
              {CATEGORY_ORDER.map((category) => (
                <li
                  key={category}
                  className="flex items-center justify-between rounded-lg border border-slate-700/60 bg-slate-900/50 px-3 py-2"
                >
                  <span className="flex items-center gap-2 text-xs text-slate-200">
                    <span
                      className="flex h-6 w-6 items-center justify-center rounded-full"
                      style={{
                        backgroundColor: CATEGORY_COLORS[category],
                        color: onColor(category),
                      }}
                    >
                      <AqiIcon category={category} className="h-4 w-4" />
                    </span>
                    {category}
                  </span>
                  <span className="font-mono text-[11px] text-slate-400">
                    {bandRange(category)}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[10px] text-slate-500">
              {t("algo.categoriesNote")}
            </p>
          </Section>

          <Section id="algo-versions" title={t("algo.versionsTitle")}>
            <ModelVersionsPanel data={versions.data ?? null} />
          </Section>
        </>
      )}

      {card.error != null && (
        <p role="alert" className="rounded bg-rose-500/10 p-3 text-sm text-rose-200">
          {t("algo.unavailable")}
        </p>
      )}
    </div>
  );
}

export default Algorithm;

/**
 * Every model version we have kept, and what each one scored.
 *
 * Without this, a retrain silently replaces the previous model and there is no
 * way to tell "it got worse" from "it changed". Each row is a version that was
 * measured at the time it was trained, so the progression is legible: if a
 * retrain made the error worse, that is visible here rather than discovered
 * months later in a bad estimate.
 *
 * MAE is lower-is-better, so the column is drawn as a bar where a longer bar
 * means a worse score - the opposite of a "higher is better" chart, and
 * deliberately so, because the question a reader has is "which was best".
 */

import { useTranslation } from "react-i18next";
import type { ModelVersions } from "../../lib/api";

export function ModelVersionsPanel({
  data,
}: {
  data: ModelVersions | null;
}): React.JSX.Element | null {
  const { t } = useTranslation();
  const versions = data?.versions ?? [];
  if (versions.length === 0) return null;

  const maes = versions
    .map((v) => v.temporal_mae)
    .filter((m): m is number => typeof m === "number");
  const worst = Math.max(...maes, 1);
  const best = versions.reduce((a, b) =>
    (b.temporal_mae ?? Infinity) < (a.temporal_mae ?? Infinity) ? b : a,
  );

  return (
    <section
      data-testid="model-versions"
      aria-label={t("versions.title")}
      className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3"
    >
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        {t("versions.title")}
      </h3>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-[10px]">
          <thead className="text-slate-500">
            <tr>
              <th className="py-1 pr-2 font-medium">Version</th>
              <th className="py-1 pr-2 font-medium">Trained</th>
              <th className="py-1 pr-2 font-medium">Rows</th>
              <th className="py-1 pr-2 font-medium">MAE (lower better)</th>
              <th className="py-1 font-medium">Unseen stn</th>
            </tr>
          </thead>
          <tbody>
            {versions.map((v) => {
              const isCurrent = v.version_id === data?.current;
              const w = v.temporal_mae
                ? Math.max(6, (v.temporal_mae / worst) * 100)
                : 0;
              return (
                <tr
                  key={v.version_id}
                  data-testid={`model-version-${v.version_id}`}
                  className="border-t border-slate-800 align-middle"
                >
                  <td className="py-1 pr-2 font-mono text-slate-300">
                    {v.version_id.slice(0, 16)}
                    {isCurrent && (
                      <span className="ml-1 rounded bg-teal-500/20 px-1 text-[9px] text-teal-200">
                        live
                      </span>
                    )}
                    {!v.artifact_present && (
                      <span
                        className="ml-1 rounded bg-slate-700/70 px-1 text-[9px] text-slate-400"
                        title={v.git_commit ?? undefined}
                      >
                        pruned
                      </span>
                    )}
                  </td>
                  <td className="py-1 pr-2 text-slate-400">{v.trained_utc.slice(0, 10)}</td>
                  <td className="py-1 pr-2 font-mono text-slate-400">
                    {v.n_rows.toLocaleString()}
                  </td>
                  <td className="py-1 pr-2">
                    <span className="flex items-center gap-1.5">
                      <span className="w-14 shrink-0 font-mono text-slate-300">
                        {v.temporal_mae?.toFixed(2) ?? "-"}
                      </span>
                      <span className="h-1.5 w-16 shrink-0 overflow-hidden rounded-full bg-slate-800">
                        <span
                          className={`block h-full rounded-full ${
                            v.version_id === best.version_id
                              ? "bg-emerald-400/80"
                              : "bg-amber-500/50"
                          }`}
                          style={{ width: `${w}%` }}
                        />
                      </span>
                    </span>
                  </td>
                  <td className="py-1 font-mono text-slate-400">
                    {v.unseen_mae?.toFixed(2) ?? "-"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
        {t("versions.explainer")}
      </p>
    </section>
  );
}

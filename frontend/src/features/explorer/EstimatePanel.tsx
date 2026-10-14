import { useTranslation } from "react-i18next";
import AqiIcon from "../../components/AqiIcon";
import { CATEGORY_COLORS, onColor } from "../../lib/aqi";
import { ApiError, type Estimate } from "../../lib/api";

/** The estimate card: value, interval, category, station, age, honesty. */
export function EstimatePanel({
  estimate,
  loading,
  error,
  compact = false,
}: {
  estimate?: Estimate;
  loading: boolean;
  error?: Error | null;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  if (loading) return <div className="skeleton h-24 rounded bg-white/5" aria-busy="true" />;
  if (error)
    return (
      <div role="alert" data-testid="estimate-error" className="p-3 rounded bg-red-950/60 text-sm">
        {/* the API's own RFC 9457 detail explains the real reason (e.g. the
            point is outside the Delhi-NCR coverage polygon) */}
        <p>
          {error instanceof ApiError && error.problem.detail
            ? error.problem.detail
            : t("explorer.error")}
        </p>
        <button
          type="button"
          className="mt-2 px-3 min-h-touch rounded bg-white/10"
          onClick={() => window.location.reload()}
        >
          {t("explorer.retry")}
        </button>
      </div>
    );
  if (!estimate) return null;

  const color = CATEGORY_COLORS[estimate.category] ?? "#64748b";
  const ageMinutes = Math.round(estimate.data_age_seconds / 60);

  return (
    <section aria-labelledby="estimate-heading" data-testid="estimate-panel">
      <div
        className="flex items-center gap-3 rounded-xl p-3 ring-1 ring-inset"
        style={{ backgroundColor: `${color}1f`, borderColor: `${color}55` }}
      >
        <span
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full"
          style={{ backgroundColor: color, color: onColor(estimate.category) }}
        >
          <AqiIcon category={estimate.category} className="h-6 w-6" />
        </span>
        <div className="min-w-0">
          <h2 id="estimate-heading" className="text-xs text-slate-300">
            {t("explorer.estimate")}
          </h2>
          <div className="flex items-baseline gap-2">
            <span data-testid="estimate-value" className="text-4xl font-bold leading-none text-white">
              {estimate.pm25_mid.toFixed(0)}
            </span>
            <span className="text-sm text-slate-400">µg/m³</span>
          </div>
        </div>
        <span
          data-testid="estimate-category"
          className="ml-auto rounded-full px-2.5 py-1 text-center text-[11px] font-semibold leading-tight"
          style={{ backgroundColor: color, color: onColor(estimate.category) }}
        >
          {t(`categories.${estimate.category}` as never)}
        </span>
      </div>
      <div className="mb-2 mt-1 flex flex-wrap items-center gap-1.5 text-[10px]">
        <span
          data-testid="served-by-chip"
          className={`rounded-full px-2 py-0.5 font-medium ${
            estimate.served_by === "model"
              ? "bg-emerald-500/15 text-emerald-300"
              : "bg-slate-700/60 text-slate-300"
          }`}
        >
          {estimate.served_by === "model" ? "model estimate" : "nearest-station baseline"}
        </span>
      </div>
      <p className="text-sm text-slate-400 mt-1">
        {t("explorer.interval")}: {estimate.pm25_low.toFixed(0)} – {estimate.pm25_high.toFixed(0)}
      </p>
      <p className="mt-2 text-xs leading-relaxed text-slate-400" data-testid="honesty">
        <span className="mb-1 block font-medium text-slate-300">
          {t("explorer.honesty")}
        </span>
        {estimate.honesty}
      </p>
      {estimate.stale && (
        <p className="text-xs text-amber-300 mt-1" role="status">
          {t("explorer.stale")}
        </p>
      )}
      {!compact && (
        <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div>
            <dt className="text-slate-400">{t("explorer.station")}</dt>
            <dd data-testid="station-reading">
              {estimate.nearest_station_name ?? "—"}
              {estimate.nearest_station_pm25
                ? ` — ${estimate.nearest_station_pm25.toFixed(0)} µg/m³`
                : ""}
            </dd>
          </div>
          <div>
            <dt className="text-slate-400">{t("explorer.dataAge")}</dt>
            <dd>
              {ageMinutes < 60
                ? t("explorer.minutesAgo", { count: ageMinutes })
                : t("explorer.hoursAgo", { count: Math.round(ageMinutes / 60) })}
            </dd>
          </div>
          <div>
            <dt className="text-slate-400">{t("explorer.servedBy")}</dt>
            <dd data-testid="served-by">{estimate.served_by}</dd>
          </div>
          <div>
            <dt className="text-slate-400">{t("explorer.modelVersion")}</dt>
            <dd>{estimate.model_version}</dd>
          </div>
        </dl>
      )}
    </section>
  );
}

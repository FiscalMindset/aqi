/**
 * An independent second opinion on the same air.
 *
 * Our estimate is anchored to the nearest CPCB monitor. CAMS, via Open-Meteo,
 * is a regional satellite-and-model average. Showing both is honest: when they
 * disagree, the reader learns that their street is dirtier (or cleaner) than
 * the regional picture instead of trusting one number blindly.
 *
 * It is deliberately presented as a model and never as a source attribution -
 * a regional aerosol grid cannot say what caused the pollution, and its dust
 * component reflects the post-monsoon dust season, not wildfire smoke.
 */

import { useTranslation } from "react-i18next";
import type { CrossCheck } from "../../lib/api";

export function CrossCheck({
  data,
  ourPm25,
}: {
  data: CrossCheck | null;
  ourPm25: number | null;
}): React.JSX.Element {
  const { t } = useTranslation();

  if (!data || data.pm25_ugm3 == null) {
    return (
      <section
        data-testid="cross-check-unavailable"
        aria-label={t("crosscheck.title")}
        className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3"
      >
        <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          {t("crosscheck.title")}
        </h3>
        <p className="text-[11px] text-slate-500">{t("crosscheck.unavailable")}</p>
      </section>
    );
  }

  const delta = data.delta_ugm3;
  // Below ~20 ug/m3 the two are close enough that flagging it would be noise.
  const significant = delta != null && Math.abs(delta) >= 20;

  return (
    <section
      data-testid="cross-check"
      aria-label={t("crosscheck.title")}
      className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3"
    >
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        {t("crosscheck.title")}
      </h3>

      <div className="grid grid-cols-2 gap-2">
        <Tile label={t("crosscheck.yours")} value={ourPm25} tone="ours" />
        <Tile label={t("crosscheck.cams")} value={data.pm25_ugm3} tone="cams" />
      </div>

      {delta != null && (
        <p className="mt-2 text-[11px] text-slate-400">
          {t("crosscheck.gap")}:{" "}
          <span
            className={`font-mono ${significant ? "text-amber-300" : "text-slate-300"}`}
          >
            {delta > 0 ? "+" : ""}
            {delta.toFixed(1)} µg/m³
          </span>
        </p>
      )}

      {data.dust_ugm3 != null && data.dust_ugm3 >= 40 && (
        <p
          data-testid="cross-check-dust"
          className="mt-1.5 text-[10px] text-amber-200/90"
        >
          {t("crosscheck.dustNote")} ({data.dust_ugm3.toFixed(0)} µg/m³)
        </p>
      )}

      <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
        {t("crosscheck.explainer")}
      </p>
    </section>
  );
}

function Tile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | null;
  tone: "ours" | "cams";
}): React.JSX.Element {
  return (
    <div className="rounded-lg bg-slate-800/60 px-2.5 py-2">
      <div className="text-[10px] leading-tight text-slate-500">{label}</div>
      <div
        className={`mt-0.5 font-mono text-base ${
          tone === "ours" ? "text-emerald-300" : "text-slate-100"
        }`}
      >
        {value == null ? "—" : value.toFixed(0)}
        {value != null && <span className="ml-0.5 text-[10px] text-slate-500">µg/m³</span>}
      </div>
    </div>
  );
}
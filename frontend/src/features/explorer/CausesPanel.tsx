import { useTranslation } from "react-i18next";
import type { Attribution } from "../../lib/api";

/** Ranked likely causes with bands and expandable evidence. */
export function CausesPanel({ attribution }: { attribution: Attribution }) {
  const { t } = useTranslation();
  const byId = new Map(attribution.evidence.map((e) => [e.evidence_id, e]));

  return (
    <section aria-labelledby="causes-heading" data-testid="causes-panel">
      <h3 id="causes-heading" className="font-semibold">
        {t("explorer.likelyCauses")}
      </h3>
      <p className="text-xs text-slate-400 mb-2">{t("explorer.causesDisclaimer")}</p>
      {attribution.likely_causes.length === 0 && (
        <p className="text-sm text-slate-400">{t("explorer.noCauses")}</p>
      )}
      <ol className="space-y-2">
        {attribution.likely_causes.map((cause) => (
          <li key={cause.rank} className="rounded bg-white/5 p-3">
            <div className="flex items-center gap-2">
              <span
                className={`text-xs font-bold px-2 py-0.5 rounded ${
                  cause.band === "High"
                    ? "bg-red-700"
                    : cause.band === "Medium"
                      ? "bg-amber-600"
                      : "bg-slate-600"
                }`}
              >
                {cause.band}
              </span>
              <span className="font-medium text-sm">{cause.label}</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">{cause.reasoning}</p>
            <details className="mt-1">
              <summary className="text-xs text-slate-400 cursor-pointer">
                {t("explorer.evidence")}
              </summary>
              <ul className="mt-1 space-y-1">
                {cause.evidence_ids.map((id) => {
                  const ev = byId.get(id);
                  if (!ev) return null;
                  return (
                    <li key={id} className="text-xs text-slate-400">
                      <span className="font-mono text-slate-300">{ev.tool}</span>:{" "}
                      {ev.summary}
                      {!ev.ok && <span className="text-amber-300"> (failed)</span>}
                    </li>
                  );
                })}
              </ul>
            </details>
          </li>
        ))}
      </ol>
      <p className="text-xs text-slate-400 mt-2">
        Confidence: {attribution.confidence} — {attribution.confidence_reason}
      </p>
    </section>
  );
}

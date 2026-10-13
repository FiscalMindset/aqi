import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useExplain } from "../../hooks/useApi";

const DELHI = { lat: 28.6139, lon: 77.209 };

const STEP_COUNT = 4;

/** Interactive walkthrough: agent trace + upwind cone, step by step. */
export function HowItWorks() {
  const { t } = useTranslation();
  const [step, setStep] = useState(0);
  const explain = useExplain(DELHI.lat, DELHI.lon);
  const evidence = explain.data?.attribution.evidence ?? [];

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4" data-testid="how-it-works">
      <h1 className="text-xl font-bold">{t("how.title")}</h1>
      <p className="text-sm text-slate-400">
        {t("how.step", { n: step + 1 })} {t("how.of")} {STEP_COUNT}
      </p>
      {step === 0 && (
        <div className="rounded bg-white/5 p-4 text-sm">
          <h2 className="font-semibold">1. Estimate the air</h2>
          <p>
            A gradient-boosting model predicts PM2.5 for every H3 res-8 cell
            from weather, calendar, nearby OpenStreetMap sources and the nearest
            station's recent history. The result always carries an 80% interval.
          </p>
        </div>
      )}
      {step === 1 && (
        <div className="rounded bg-white/5 p-4 text-sm">
          <h2 className="font-semibold">2. Look upwind</h2>
          <p>
            The wind direction selects a cone. OpenSearch returns landfills,
            industrial areas, construction sites and junctions inside it, each
            with a transparent influence score.{" "}
            <em>Heuristic ranking, not causal proof.</em>
          </p>
        </div>
      )}
      {step === 2 && (
        <div className="rounded bg-white/5 p-4 text-sm">
          <h2 className="font-semibold">3. Explain with evidence</h2>
          <ol className="list-decimal pl-5">
            {evidence.map((ev) => (
              <li key={ev.evidence_id} className="mt-1">
                <span className="font-mono text-teal-300">{ev.tool}</span> — {ev.summary}
              </li>
            ))}
            {evidence.length === 0 && <li>Loading the live trace…</li>}
          </ol>
        </div>
      )}
      {step === 3 && (
        <div className="rounded bg-white/5 p-4 text-sm">
          <h2 className="font-semibold">4. Act on it</h2>
          <p>
            Advice for parents, riders and outdoor workers, plus alerts when the
            estimate crosses your chosen category. Every number on this site is
            an estimate, not a measurement.
          </p>
        </div>
      )}
      <div className="flex gap-2">
        <button
          type="button"
          className="min-h-touch px-4 rounded bg-white/10"
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
        >
          {t("how.prev")}
        </button>
        <button
          type="button"
          className="min-h-touch px-4 rounded bg-teal-700"
          onClick={() => setStep((s) => Math.min(STEP_COUNT - 1, s + 1))}
          disabled={step === STEP_COUNT - 1}
        >
          {t("how.next")}
        </button>
        <button
          type="button"
          className="min-h-touch px-4 rounded bg-white/10"
          onClick={() => setStep(0)}
        >
          {t("how.restart")}
        </button>
      </div>
    </div>
  );
}

export default HowItWorks;

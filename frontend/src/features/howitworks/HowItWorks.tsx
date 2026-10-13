/**
 * How it works.
 *
 * A stepper that reads as a marketing funnel is not useful to anyone deciding
 * whether to trust a number. This walks the actual pipeline against the actual
 * point on screen, and at every step it shows what the system really knows: the
 * tools it called, the evidence they returned, the sources it found, and the
 * model's own measured error.
 *
 * The walkthrough fetches live data for a fixed Delhi point rather than using
 * hardcoded examples, so if a feed breaks this page goes quiet instead of
 * continuing to describe a pipeline that no longer exists.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useExplain, useValidation } from "../../hooks/useApi";

const DELHI = { lat: 28.6139, lon: 77.209 };
const STEP_COUNT = 4;

const STEPS = [
  { id: "estimate", title: "Estimate the air", blurb: "Anchor, adjust, calibrate" },
  { id: "sources", title: "Look upwind", blurb: "Only what the wind carries to you" },
  { id: "explain", title: "Explain with evidence", blurb: "Every sentence cites a passage" },
  { id: "act", title: "Act on it", blurb: "Routes and alerts" },
] as const;

function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg bg-slate-800/60 p-3">
      <p className="text-[11px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 font-mono text-lg">{value}</p>
      {note && <p className="mt-0.5 text-[11px] text-slate-500">{note}</p>}
    </div>
  );
}

export function HowItWorks() {
  const { t } = useTranslation();
  const [step, setStep] = useState(0);
  const explain = useExplain(DELHI.lat, DELHI.lon);
  const validation = useValidation();

  const attribution = explain.data?.attribution;
  const evidence = attribution?.evidence ?? [];
  const causes = attribution?.likely_causes ?? [];
  const paras = explain.data?.paragraphs ?? [];
  const passages = explain.data?.passages ?? [];
  const gaps = explain.data?.evidence_gaps ?? [];
  const th = validation.data?.temporal_holdout;
  const loso = validation.data?.loso_mean;

  return (
    <div className="mx-auto max-w-4xl space-y-5 p-4" data-testid="how-it-works">
      <header>
        <h1 className="text-xl font-bold">{t("how.title")}</h1>
        <p className="mt-1 text-sm text-slate-400">
          Four steps, run live against a fixed point in central Delhi. The
          numbers and tool calls below are real responses from the API, not
          examples.
        </p>
      </header>

      <ol className="grid gap-2 sm:grid-cols-4">
        {STEPS.map((s, i) => (
          <li key={s.id}>
            <button
              type="button"
              data-testid={`how-step-${s.id}`}
              aria-current={i === step ? "step" : undefined}
              onClick={() => setStep(i)}
              className={`w-full rounded-lg border p-3 text-left transition ${
                i === step
                  ? "border-teal-500/60 bg-teal-500/10"
                  : "border-white/10 bg-slate-900/40 hover:border-white/20"
              }`}
            >
              <span className="font-mono text-[10px] text-slate-500">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="mt-0.5 block text-sm font-medium">{s.title}</span>
              <span className="mt-0.5 block text-[11px] text-slate-400">{s.blurb}</span>
            </button>
          </li>
        ))}
      </ol>

      {step === 0 && (
        <section className="space-y-3">
          <p className="text-sm leading-relaxed text-slate-300">
            A model predicts the next hour for any point. It does not start from
            nothing: it takes the nearest official station&rsquo;s reading from
            about an hour ago as an anchor, learns what weather, time of day and
            nearby sources typically move that number, and applies the
            correction. That is why the estimate is anchored to something real
            rather than extrapolated from thin air.
          </p>
          <p className="text-sm leading-relaxed text-slate-300">
            The output is a point and an 80% interval. The interval is calibrated
            on held-out residuals, so it widens where the model is genuinely less
            certain instead of pretending to a precision it does not have.
          </p>
          <div className="grid gap-2 sm:grid-cols-3">
            <Metric
              label="Unseen-station error"
              value={loso?.mae != null ? `${loso.mae.toFixed(1)} µg/m³` : "—"}
              note="leave-one-station-out; the case you are in"
            />
            <Metric
              label="Next-hour error"
              value={th?.mae != null ? `${th.mae.toFixed(1)} µg/m³` : "—"}
              note="at stations it trained on"
            />
            <Metric
              label="Persistence baseline"
              value="same value an hour ago"
              note="the thing we must beat"
            />
          </div>
        </section>
      )}

      {step === 1 && (
        <section className="space-y-3">
          <p className="text-sm leading-relaxed text-slate-300">
            Air arrives with the wind. So the sources that matter are the ones in
            the upwind cone of your point — not the ones nearest to it. A landfill
            four kilometres downwind cannot be why your street is dirty.
          </p>
          <p className="text-sm leading-relaxed text-slate-300">
            Every source is an OpenStreetMap feature classified into a category,
            scored by distance, bearing against the wind direction, and type
            weight. The score is transparent and it is a heuristic ranking, not a
            measurement of emissions.
          </p>
          <ul className="space-y-1.5" data-testid="how-causes">
            {causes.length === 0 && (
              <li className="text-sm text-slate-400">
                {explain.isPending ? "Running the attribution…" : "No source was upwind of this point right now."}
              </li>
            )}
            {causes.map((c) => (
              <li
                key={c.label + c.category}
                className="flex flex-wrap items-baseline gap-2 rounded-lg bg-slate-800/60 px-3 py-2 text-sm"
              >
                <span className="font-medium">{c.label}</span>
                <span className="text-xs text-slate-400">{c.reasoning}</span>
                <span
                  className={`ml-auto text-[11px] uppercase ${
                    c.band === "High"
                      ? "text-rose-300"
                      : c.band === "Medium"
                        ? "text-amber-300"
                        : "text-slate-400"
                  }`}
                >
                  {c.band}
                </span>
              </li>
            ))}
          </ul>
          {gaps.length > 0 && (
            <p className="rounded bg-amber-500/10 p-2.5 text-xs text-amber-200">
              {gaps.join(", ")} did not answer, so anything that depended on them
              is omitted above rather than guessed.
            </p>
          )}
        </section>
      )}

      {step === 2 && (
        <section className="space-y-3">
          <p className="text-sm leading-relaxed text-slate-300">
            The explanation is written from retrieved evidence, not generated
            freely. Each paragraph carries the ids of the passages it was
            composed from, and a guard rejects any answer that cites something
            that was not actually retrieved.
          </p>
          <div className="grid gap-3 lg:grid-cols-2">
            <div>
              <h3 className="mb-1.5 text-sm font-semibold text-slate-300">
                Passages in the answer
              </h3>
              <ul className="space-y-1" data-testid="how-passages">
                {paras.length === 0 && (
                  <li className="text-sm text-slate-400">
                    {explain.isPending ? "Composing…" : "No explanation produced."}
                  </li>
                )}
                {paras.map((p) => (
                  <li key={p.intent} className="rounded bg-slate-800/60 p-2.5 text-xs">
                    <span className="font-medium text-slate-300">{p.intent}</span>
                    <p className="mt-0.5 text-slate-400">{p.text}</p>
                    <p className="mt-1 font-mono text-[10px] text-slate-500">
                      cites {p.passage_ids.join(", ")}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="mb-1.5 text-sm font-semibold text-slate-300">
                Tools this run called
              </h3>
              <ol className="space-y-1" data-testid="how-evidence">
                {evidence.length === 0 && (
                  <li className="text-sm text-slate-400">
                    {explain.isPending ? "Calling tools…" : "No tools returned."}
                  </li>
                )}
                {evidence.map((ev) => (
                  <li key={ev.evidence_id} className="rounded bg-slate-800/60 p-2.5 text-xs">
                    <span className="font-mono text-teal-300">{ev.tool}</span>
                    {ev.ok ? (
                      <span className="text-slate-400"> — {ev.summary}</span>
                    ) : (
                      <span className="text-rose-300"> — failed: {ev.note ?? "unknown"}</span>
                    )}
                    <p className="mt-0.5 font-mono text-[10px] text-slate-500">
                      {ev.evidence_id} · {passages.length} passages in the answer
                    </p>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>
      )}

      {step === 3 && (
        <section className="space-y-3">
          <p className="text-sm leading-relaxed text-slate-300">
            Knowing the air is bad is only half of it. The cleanest-route
            comparison profiles several real roads with the same model and ranks
            them by exposure rather than distance, so a slightly longer route can
            come out ahead. The subscription alerts you when the estimate for a
            point crosses into a band you chose.
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-lg border border-white/10 bg-slate-900/40 p-3">
              <h3 className="text-sm font-semibold">Cleanest route</h3>
              <p className="mt-1 text-xs text-slate-400">
                Ranked by mean exposure along the road, sampled every few
                hundred metres. The exposure index multiplies that mean by time
                in the vehicle, so a clean but slow detour is not automatically
                better.
              </p>
            </div>
            <div className="rounded-lg border border-white/10 bg-slate-900/40 p-3">
              <h3 className="text-sm font-semibold">Alerts</h3>
              <p className="mt-1 text-xs text-slate-400">
                One email when the estimate crosses your chosen CPCB band. You can
                preview the real email before subscribing.
              </p>
            </div>
          </div>
          <p className="rounded border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-slate-300">
            Every number this site shows is an estimate with an interval, not a
            measurement of your exact spot. Official CPCB stations remain the
            authoritative source, and we link to them.
          </p>
        </section>
      )}

      <div className="flex gap-2 pt-1">
        <button
          type="button"
          data-testid="how-back"
          disabled={step === 0}
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          className="min-h-touch rounded border border-white/20 px-4 py-2 text-sm disabled:opacity-40"
        >
          {t("how.back")}
        </button>
        <button
          type="button"
          data-testid="how-next"
          disabled={step === STEP_COUNT - 1}
          onClick={() => setStep((s) => Math.min(STEP_COUNT - 1, s + 1))}
          className="min-h-touch rounded bg-teal-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
        >
          {t("how.next")}
        </button>
        <button
          type="button"
          data-testid="how-restart"
          onClick={() => setStep(0)}
          className="min-h-touch rounded border border-white/20 px-4 py-2 text-sm"
        >
          {t("how.restart")}
        </button>
        <span className="ml-auto self-center text-xs text-slate-500">
          {t("how.step", { n: step + 1 })} {t("how.of")} {STEP_COUNT}
        </span>
      </div>
    </div>
  );
}

export default HowItWorks;
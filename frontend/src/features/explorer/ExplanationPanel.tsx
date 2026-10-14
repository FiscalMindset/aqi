/**
 * The cited explanation.
 *
 * The prose was correct but it read as a wall: one long paragraph of numbers
 * that a person has to decode. This splits it into cards with an icon, a
 * heading and at most two sentences each, ordered so the most important thing
 * is first. Every card still carries the ids of the passages it came from, and
 * opens to show them.
 *
 * The rule that produced the original text is unchanged - a card only exists if
 * a passage for it was actually retrieved, so nothing here can appear without
 * evidence behind it.
 */

import { useState } from "react";
import type { ExplanationParagraph, Passage } from "../../lib/api";

const KIND_META: Record<string, { label: string; icon: string; tint: string; border: string }> = {
  model_estimate: {
    label: "The number",
    icon: "◎",
    tint: "bg-teal-500/10",
    border: "border-teal-500/30",
  },
  station_reading: {
    label: "Measured nearby",
    icon: "◉",
    tint: "bg-emerald-500/10",
    border: "border-emerald-500/30",
  },
  station_trend: {
    label: "Trend",
    icon: "↗",
    tint: "bg-sky-500/10",
    border: "border-sky-500/30",
  },
  source_upwind: {
    label: "Upwind of you",
    icon: "↑",
    tint: "bg-orange-500/10",
    border: "border-orange-500/30",
  },
  source_nearby: {
    label: "Nearby source",
    icon: "•",
    tint: "bg-slate-500/10",
    border: "border-slate-500/30",
  },
  wind: {
    label: "Wind",
    icon: "≈",
    tint: "bg-cyan-500/10",
    border: "border-cyan-500/30",
  },
  ventilation: {
    label: "Ventilation",
    icon: "☁",
    tint: "bg-cyan-500/10",
    border: "border-cyan-500/30",
  },
  model_parameters: {
    label: "What moved it",
    icon: "⚖",
    tint: "bg-violet-500/10",
    border: "border-violet-500/30",
  },
  fire_activity: {
    label: "Fire activity",
    icon: "▲",
    tint: "bg-red-500/10",
    border: "border-red-500/30",
  },
  model_accuracy: {
    label: "How accurate",
    icon: "✓",
    tint: "bg-indigo-500/10",
    border: "border-indigo-500/30",
  },
  freshness: {
    label: "How fresh",
    icon: "⏱",
    tint: "bg-amber-500/10",
    border: "border-amber-500/30",
  },
  cpcb_band: {
    label: "What the band means",
    icon: "≡",
    tint: "bg-emerald-500/10",
    border: "border-emerald-500/30",
  },
};

const KIND_FOR_INTENT: Record<string, string> = {
  "what we estimate here": "model_estimate",
  "what is being measured nearby": "station_reading",
  "is it getting better or worse": "station_trend",
  "what is upwind of here": "source_upwind",
  "what is close to here": "source_nearby",
  "which way the air is moving": "wind",
  "what moved that estimate": "model_parameters",
  "whether anything is burning": "fire_activity",
  "how much to trust it": "model_accuracy",
  "how old the inputs are": "freshness",
  "what the category means": "cpcb_band",
};

const FALLBACK = {
  label: "Detail",
  icon: "·",
  tint: "bg-white/5",
  border: "border-white/10",
};

export function ExplanationPanel({
  headline,
  paragraphs,
  passages,
  gaps,
  servedBy,
}: {
  headline: string;
  paragraphs: ExplanationParagraph[];
  passages: Passage[];
  gaps: string[];
  servedBy: string;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const byId = new Map(passages.map((p) => [p.passage_id, p]));

  return (
    <section aria-labelledby="explanation-heading" className="space-y-2" data-testid="explanation">
      <h2 id="explanation-heading" className="text-sm font-semibold uppercase tracking-wide text-slate-400">
        Why this reading
      </h2>

      <p
        className="rounded-xl border border-teal-500/30 bg-teal-500/10 p-3 text-base font-medium"
        data-testid="explanation-headline"
      >
        {headline}
      </p>

      {paragraphs.map((para, i) => {
        const kind = KIND_FOR_INTENT[para.intent] ?? "other";
        const meta = KIND_META[kind] ?? FALLBACK;
        const open = openId === para.intent;
        return (
          <article
            key={`${para.intent}-${i}`}
            data-testid={`explain-card-${kind}`}
            className={`rounded-xl border p-3 ${meta.border} ${meta.tint}`}
          >
            <div className="flex items-baseline gap-2">
              <span aria-hidden="true" className="text-sm text-slate-200">
                {meta.icon}
              </span>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-300">
                {meta.label}
              </h3>
              <button
                type="button"
                className="ml-auto text-[11px] text-slate-400 underline underline-offset-2 hover:text-slate-200"
                aria-expanded={open}
                onClick={() => setOpenId(open ? null : para.intent)}
                data-testid={`evidence-toggle-${kind}`}
              >
                {open ? "hide" : "evidence"}
              </button>
            </div>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-100">{para.text}</p>

            {open && (
              <ul className="mt-2 space-y-1.5 border-t border-white/10 pt-2">
                {para.passage_ids.map((id) => {
                  const p = byId.get(id);
                  if (!p) return null;
                  return (
                    <li key={id} className="rounded bg-night-900/40 p-2 text-[11px] text-slate-300">
                      <span className="font-mono text-slate-400">{p.passage_id}</span>
                      {p.measured && (
                        <span className="ml-1.5 rounded bg-emerald-500/20 px-1 text-emerald-300">
                          measured
                        </span>
                      )}
                      <span className="ml-1.5 text-slate-500">
                        weight {p.authority.toFixed(2)}
                      </span>
                      <p className="mt-0.5">{p.text}</p>
                      {p.source_url && (
                        <a
                          href={p.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-teal-300 underline underline-offset-2"
                        >
                          source ↗
                        </a>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </article>
        );
      })}

      {gaps.length > 0 && (
        <div
          role="status"
          data-testid="evidence-gaps"
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-100"
        >
          <p className="font-semibold">Some inputs did not answer</p>
          <p className="mt-1 text-amber-200/90">
            No {gaps.join(", no ")}. Anything that depended on them is left out
            above rather than guessed.
          </p>
        </div>
      )}

      <p className="pt-1 text-[11px] text-slate-500">
        Written from retrieved evidence
        {servedBy.includes("groq") ? ", lightly rephrased by a language model" : ""}.
        Every number came from a cited passage.
      </p>
    </section>
  );
}

export default ExplanationPanel;
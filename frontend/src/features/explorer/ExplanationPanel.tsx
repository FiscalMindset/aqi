/**
 * The cited explanation.
 *
 * Every paragraph carries the ids of the passages it was composed from, so the
 * panel can show the workings rather than asking for trust. The passage list is
 * the audit trail: a measured station reading and a model output look different
 * here, and a paragraph whose evidence is missing is visibly unbacked.
 */

import { useState } from "react";
import type { ExplanationParagraph, Passage } from "../../lib/api";

const KIND_LABEL: Record<string, string> = {
  station_reading: "Official measurement",
  station_trend: "Trend",
  model_estimate: "Our estimate",
  cpcb_band: "CPCB band",
  model_parameters: "Model parameters",
  model_accuracy: "Measured accuracy",
  source_upwind: "Upwind source",
  source_nearby: "Nearby source",
  wind: "Wind",
  ventilation: "Derived from wind",
  fire_activity: "Fire detections",
  freshness: "Data age",
};

const INTENT_ORDER = [
  "what we estimate here",
  "what is being measured nearby",
  "is it getting better or worse",
  "what is upwind of here",
  "what is close to here",
  "which way the air is moving",
  "what moved that estimate",
  "whether anything is burning",
  "how much to trust it",
  "how old the inputs are",
  "what the category means",
];

function orderOf(intent: string): number {
  const i = INTENT_ORDER.indexOf(intent);
  return i === -1 ? INTENT_ORDER.length : i;
}

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
  const sorted = [...paragraphs].sort((a, b) => orderOf(a.intent) - orderOf(b.intent));

  return (
    <section aria-labelledby="explanation-heading" className="space-y-3">
      <h2 id="explanation-heading" className="text-sm font-semibold">
        What this means
      </h2>

      <p className="text-base font-medium" data-testid="explanation-headline">
        {headline}
      </p>

      {sorted.map((para) => {
        const open = openId === para.intent;
        return (
          <div key={para.intent} className="rounded-lg border border-line bg-surface-2 p-3">
            <p className="text-sm leading-relaxed">{para.text}</p>
            <button
              type="button"
              className="mt-2 text-xs text-accent underline underline-offset-2"
              aria-expanded={open}
              onClick={() => setOpenId(open ? null : para.intent)}
            >
              {open ? "Hide evidence" : `Show evidence (${para.passage_ids.length})`}
            </button>
            {open && (
              <ul className="mt-2 space-y-1.5">
                {para.passage_ids.map((id) => {
                  const p = byId.get(id);
                  if (!p) return null;
                  return (
                    <li key={id} className="rounded bg-surface-3 p-2 text-xs">
                      <span className="font-medium">{KIND_LABEL[p.kind] ?? p.kind}</span>
                      {p.measured && <span className="ml-1 text-emerald-400">measured</span>}
                      <p className="mt-0.5 text-muted">{p.text}</p>
                      <p className="mt-0.5 text-muted">
                        confidence weight {p.authority.toFixed(2)}
                        {p.source_url && (
                          <>
                            {" · "}
                            <a
                              href={p.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="underline underline-offset-2"
                            >
                              source
                            </a>
                          </>
                        )}
                      </p>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}

      {gaps.length > 0 && (
        <div
          role="status"
          className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs"
        >
          <p className="font-medium">Some inputs did not answer</p>
          <p className="mt-1 text-muted">
            No {gaps.join(", no ")}. Anything that depended on them is left out above rather
            than guessed.
          </p>
        </div>
      )}

      <p className="text-xs text-muted">
        Written from retrieved evidence
        {servedBy.includes("groq") ? " and lightly rephrased by a language model" : ""}.
        Every number above came from a cited passage.
      </p>
    </section>
  );
}

export default ExplanationPanel;
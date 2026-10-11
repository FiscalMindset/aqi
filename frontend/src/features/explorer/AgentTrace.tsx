import { useTranslation } from "react-i18next";
import type { UseQueryResult } from "@tanstack/react-query";
import type { ExplainResponse } from "../../lib/api";

/** "How the agent got here": the real tool-call trace, collapsed by default. */
export function AgentTrace({
  explain,
}: {
  explain: UseQueryResult<ExplainResponse, Error>;
}) {
  const { t } = useTranslation();
  if (explain.isPending) {
    return (
      <div className="skeleton h-16 rounded bg-white/5" aria-busy="true" data-testid="trace-loading" />
    );
  }
  if (explain.error) {
    return (
      <p role="alert" className="text-sm text-red-300">
        {t("explorer.error")}
      </p>
    );
  }
  const data = explain.data;
  if (!data) return null;
  const { attribution } = data;

  return (
    <section aria-labelledby="trace-heading" data-testid="agent-trace">
      <h3 id="trace-heading" className="font-semibold">
        {t("explorer.howAgentHere")}
      </h3>
      <p className="text-xs text-slate-400">
        served_by: {data.served_by} · confidence: {attribution.confidence}
      </p>
      <ol className="mt-2 space-y-1" data-testid="tool-calls">
        {attribution.evidence.map((ev, i) => (
          <li key={ev.evidence_id} className="rounded bg-white/5 p-2 text-xs">
            <span className="font-mono text-teal-300">
              {i + 1}. {ev.tool}
            </span>{" "}
            <span className="text-slate-400">{ev.fetched_at}</span>
            <p className="text-slate-300 mt-0.5">{ev.summary}</p>
            {!ev.ok && <p className="text-amber-300">{ev.note}</p>}
          </li>
        ))}
      </ol>
    </section>
  );
}

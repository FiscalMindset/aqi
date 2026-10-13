/**
 * System status.
 *
 * The point of this page is not "is it up". It is: when an estimate looks
 * wrong, can you tell *why*? Every number here is real telemetry the API
 * already exposes - feed freshness and record counts from DynamoDB, component
 * readiness, which credential path each integration actually resolved to, and
 * the provenance of the boundary polygon. Nothing is decorative.
 *
 * Deliberate: a degraded system says so in plain language rather than a green
 * tick. "FIRMS is not configured, so fire smoke is absent from attribution" is
 * more useful than "1 of 3 feeds OK".
 */

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, type StatusResponse } from "../../lib/api";
import { useStatus } from "../../hooks/useApi";

const INTEGRATION_BLURB: Record<string, string> = {
  "openaq-api": "Live OpenAQ v3 API with your own credential.",
  "openaq-public-archive": "OpenAQ public archive — no credential needed. Readings are real but a day or two old.",
  bedrock: "Amazon Bedrock writes the structured attribution.",
  "scripted-deterministic": "The attribution is composed deterministically; Bedrock is not being used.",
  "composed-grounded": "The explanation is written by the deterministic composer. No language model involved.",
  "composed-grounded+groq":
    "The explanation is composed from evidence, then lightly rephrased by Groq. It cannot introduce a number.",
};

function age(seconds: number | null): { text: string; level: "ok" | "warn" | "bad" } {
  if (seconds == null) return { text: "never", level: "bad" };
  const m = seconds / 60;
  if (m < 60) return { text: `${Math.round(m)} min ago`, level: "ok" };
  const h = m / 60;
  if (h < 24) return { text: `${h.toFixed(1)} h ago`, level: h < 6 ? "ok" : "warn" };
  return { text: `${(h / 24).toFixed(1)} days ago`, level: "bad" };
}

function Pill({ level, children }: { level: "ok" | "warn" | "bad"; children: React.ReactNode }) {
  const style = {
    ok: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    warn: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    bad: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  }[level];
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${style}`}>
      {children}
    </span>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
        {title}
      </h2>
      {children}
    </section>
  );
}

export function StatusPage() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useStatus();

  // /ready is a separate probe: it checks the dependencies the estimate needs,
  // which is a different question from whether the last ingest ran.
  const ready = useQuery({
    queryKey: ["ready"],
    queryFn: () => api.ready(),
    refetchInterval: 30_000,
  });

  if (isLoading) return <div className="p-8 text-slate-400">Loading…</div>;
  if (error || !data) {
    return (
      <div className="p-8" role="alert">
        <p className="text-rose-300">Status could not be read.</p>
      </div>
    );
  }

  const status = data as StatusResponse;
  const integrations = (status.integrations ?? {}) as Record<string, string | boolean>;
  const bbox = status.coverage?.bbox;
  const feeds = status.feeds ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4" data-testid="status-page">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-bold">{t("status.title")}</h1>
        <p className="font-mono text-xs text-slate-500">
          {status.api_version} · model {status.model_version}
        </p>
      </header>

      <div
        role="status"
        data-testid="overall"
        className={`rounded-xl border p-4 ${
          status.status === "ok"
            ? "border-emerald-500/30 bg-emerald-500/10"
            : "border-amber-500/30 bg-amber-500/10"
        }`}
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{status.status === "ok" ? "●" : "◐"}</span>
          <div>
            <p className="font-semibold">
              {status.status === "ok" ? "All feeds answering" : "Running, with degraded inputs"}
            </p>
            <p className="text-sm text-slate-300">
              {status.status === "ok"
                ? "Every configured feed returned data on its last run."
                : "Estimates are still being served. The degraded feeds below are named, and anything that depended on them is omitted from the explanation rather than guessed."}
            </p>
          </div>
        </div>
      </div>

      <Card title="What this build is actually using">
        <dl className="grid gap-2 sm:grid-cols-2">
          {Object.entries(integrations).map(([key, value]) => {
            const label = value === true ? "configured" : value === false ? "not configured" : String(value);
            return (
              <div key={key} className="rounded-lg bg-slate-800/50 p-2.5">
                <dt className="font-mono text-[11px] uppercase text-slate-400">{key}</dt>
                <dd className="mt-0.5 text-sm">
                  <Pill level={value === false ? "warn" : "ok"}>{label}</Pill>
                  {INTEGRATION_BLURB[String(value)] && (
                    <p className="mt-1.5 text-xs leading-relaxed text-slate-400">
                      {INTEGRATION_BLURB[String(value)]}
                    </p>
                  )}
                </dd>
              </div>
            );
          })}
        </dl>
      </Card>

      <Card title="Readiness probes">
        {ready.isError ? (
          <p className="text-sm text-rose-300">The readiness probe could not be read.</p>
        ) : (
          <ul className="space-y-1.5">
            {(ready.data?.checks ?? []).map((c: { component: string; ok: boolean; detail: string }) => (
              <li key={c.component} className="flex items-baseline gap-2 text-sm">
                <Pill level={c.ok ? "ok" : "bad"}>{c.ok ? "pass" : "fail"}</Pill>
                <span className="font-mono text-xs">{c.component}</span>
                <span className="text-slate-400">{c.detail}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Feed freshness">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10 text-left text-slate-400">
              <th className="pb-1.5">Feed</th>
              <th className="pb-1.5">State</th>
              <th className="pb-1.5">Age</th>
              <th className="pb-1.5 text-right">Records</th>
            </tr>
          </thead>
          <tbody>
            {feeds.map((f) => {
              const a = age(f.age_seconds);
              return (
                <tr key={f.feed} className="border-b border-white/5 align-top">
                  <td className="py-2 font-mono text-xs">{f.feed}</td>
                  <td className="py-2">
                    <Pill level={f.ok ? "ok" : "bad"}>{f.ok ? "ok" : "failing"}</Pill>
                    {f.last_error && (
                      <p className="mt-1 max-w-xs text-[11px] text-rose-300">{f.last_error}</p>
                    )}
                  </td>
                  <td className="py-2">
                    <Pill level={a.level}>{a.text}</Pill>
                    {f.last_success_at && (
                      <p className="mt-1 font-mono text-[10px] text-slate-500">
                        {f.last_success_at.replace("T", " ").slice(0, 19)}
                      </p>
                    )}
                  </td>
                  <td className="py-2 text-right font-mono">{f.records_last_run}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>

      <Card title="Coverage and provenance">
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          {bbox && (
            <div className="rounded-lg bg-slate-800/50 p-2.5">
              <dt className="text-[11px] uppercase text-slate-400">Served area</dt>
              <dd className="mt-1 font-mono text-xs">
                {bbox.min_lat.toFixed(3)}, {bbox.min_lon.toFixed(3)} →{" "}
                {bbox.max_lat.toFixed(3)}, {bbox.max_lon.toFixed(3)}
              </dd>
            </div>
          )}
          {status.coverage?.boundary_source && (
            <div className="rounded-lg bg-slate-800/50 p-2.5">
              <dt className="text-[11px] uppercase text-slate-400">Boundary</dt>
              <dd className="mt-1 text-xs">{status.coverage.boundary_source}</dd>
              <dd className="text-[11px] text-slate-500">{status.coverage.boundary_license}</dd>
            </div>
          )}
          {status.coverage?.boundary_fetched && (
            <div className="rounded-lg bg-slate-800/50 p-2.5">
              <dt className="text-[11px] uppercase text-slate-400">Boundary fetched</dt>
              <dd className="mt-1 font-mono text-xs">
                {status.coverage.boundary_fetched.replace("T", " ").slice(0, 19)}
              </dd>
            </div>
          )}
        </dl>
        <p className="mt-3 text-xs leading-relaxed text-slate-400">
          Point estimates come from OpenAQ (CC BY 4.0), the map from OpenStreetMap
          contributors (ODbL), and weather from Open-Meteo. The PM2.5 figure is
          always our model&rsquo;s estimate with an 80% interval, never a
          measurement of the exact spot.
        </p>
      </Card>
    </div>
  );
}

export default StatusPage;
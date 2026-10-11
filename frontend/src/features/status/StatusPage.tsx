import { useTranslation } from "react-i18next";
import { useStatus } from "../../hooks/useApi";

/** Feed freshness and system health (honest status page). */
export function StatusPage() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useStatus();

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4" data-testid="status-page">
      <h1 className="text-xl font-bold">{t("status.title")}</h1>
      {isLoading && <p>Loading…</p>}
      {error && <p role="alert" className="text-red-300 text-sm">{error.message}</p>}
      {data && (
        <>
          <p
            role="status"
            data-testid="overall"
            className={data.status === "ok" ? "text-teal-300" : "text-amber-300"}
          >
            {data.status === "ok" ? t("status.ok") : t("status.degraded")}
          </p>
          <h2 className="font-semibold">{t("status.feeds")}</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400">
                <th className="py-1">feed</th>
                <th>ok</th>
                <th>age</th>
                <th>records</th>
              </tr>
            </thead>
            <tbody>
              {data.feeds.map((f) => (
                <tr key={f.feed}>
                  <td className="font-mono text-xs">{f.feed}</td>
                  <td>{f.ok ? t("status.fresh") : t("status.stale")}</td>
                  <td>
                    {f.age_seconds == null
                      ? t("status.never")
                      : `${Math.round(f.age_seconds / 60)} min`}
                  </td>
                  <td>{f.records_last_run}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-slate-400">
            api {data.api_version} · model {data.model_version}
          </p>
        </>
      )}
    </div>
  );
}

export default StatusPage;

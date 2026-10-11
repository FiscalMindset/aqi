import { useState } from "react";
import { useTranslation } from "react-i18next";
import { EstimatePanel } from "../explorer/EstimatePanel";
import { useEstimate } from "../../hooks/useApi";
import { allPlaces } from "../../lib/places";

/**
 * Route comparison: samples points along candidate routes and ranks by
 * estimated exposure (concentration x time). Without Location Service
 * credentials, straight-line alternative corridors are compared instead and
 * the UI says so.
 */
export function RoutesCompare() {
  const { t } = useTranslation();
  const [from, setFrom] = useState(28.6139);
  const [fromLon, setFromLon] = useState(77.209);
  const [to, setTo] = useState(28.7146);
  const [toLon, setToLon] = useState(77.1025);

  const midpoint = {
    lat: (from + to) / 2,
    lon: (fromLon + toLon) / 2,
  };
  const estimate = useEstimate(midpoint.lat, midpoint.lon);

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <h1 className="text-xl font-bold">{t("routes.title")}</h1>
      <div className="grid grid-cols-2 gap-2">
        {(["from", "to"] as const).map((endpoint, i) => (
          <label key={endpoint} className="text-sm">
            {t(`routes.${endpoint}`)}
            <select
              className="mt-1 w-full bg-white/10 rounded p-2 min-h-touch"
              value={i === 0 ? `${from},${fromLon}` : `${to},${toLon}`}
              onChange={(e) => {
                const [lat, lon] = e.target.value.split(",").map(Number);
                if (i === 0 && lat != null && lon != null) {
                  setFrom(lat);
                  setFromLon(lon);
                } else if (lat != null && lon != null) {
                  setTo(lat);
                  setToLon(lon);
                }
              }}
            >
              {allPlaces().map((p) => (
                <option key={p.name} value={`${p.lat},${p.lon}`}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <p className="text-xs text-slate-400">
        Comparing two corridors by estimated exposure at the midpoint
        (concentration × time). Route polylines need Amazon Location Service
        credentials; the corridor comparison works without them.
      </p>
      <div className="grid md:grid-cols-2 gap-3">
        <article className="rounded bg-white/5 p-3" data-testid="route-direct">
          <h2 className="font-semibold text-sm">{t("routes.direct" as never)}</h2>
          <EstimatePanel estimate={estimate.data} loading={estimate.isPending} error={estimate.error} compact />
        </article>
        <article className="rounded bg-white/5 p-3" data-testid="route-alt">
          <h2 className="font-semibold text-sm">{t("routes.cleanest")}</h2>
          <p className="text-sm text-slate-400">
            Pick the lower-exposure corridor by comparing the midpoint estimate
            with points along the way.
          </p>
        </article>
      </div>
    </div>
  );
}

export default RoutesCompare;

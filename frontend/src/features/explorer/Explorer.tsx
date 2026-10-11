import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { SourceMap } from "./SourceMap";
import { BottomSheet } from "../../components/BottomSheet";
import { SearchBox } from "./SearchBox";
import { EstimatePanel } from "./EstimatePanel";
import { CausesPanel } from "./CausesPanel";
import { PersonaCards } from "./PersonaCards";
import { AgentTrace } from "./AgentTrace";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useEstimate, useExplain, useSources, useStations } from "../../hooks/useApi";

const DELHI = { lat: 28.6139, lon: 77.209 };

/**
 * Explorer: mobile-first. Phones render a draggable bottom sheet; tablets and
 * desktops render the side panel. Only ONE renders at a time (never duplicate
 * ids or duplicated network views).
 */
export function Explorer() {
  const params = useParams<{ lat: string; lon: string }>();
  const navigate = useNavigate();
  const isDesktop = useMediaQuery("(min-width: 768px)");

  const [point, setPoint] = useState(() => {
    if (params.lat && params.lon) {
      const lat = Number(params.lat);
      const lon = Number(params.lon);
      if (Number.isFinite(lat) && Number.isFinite(lon)) return { lat, lon };
    }
    return DELHI;
  });
  const [showTrace, setShowTrace] = useState(false);

  const estimate = useEstimate(point.lat, point.lon);
  const stations = useStations(point.lat, point.lon);
  const sources = useSources(point.lat, point.lon);
  const explain = useExplain(point.lat, point.lon, showTrace);

  function selectPlace(lat: number, lon: number) {
    setPoint({ lat, lon });
    navigate(`/place/${lat}/${lon}`, { replace: true });
  }

  const panel = (
    <div className="space-y-4">
      <EstimatePanel estimate={estimate.data} loading={estimate.isPending} error={estimate.error} />
      <button
        type="button"
        data-testid="explain-toggle"
        aria-expanded={showTrace}
        onClick={() => setShowTrace((v) => !v)}
        className="w-full min-h-touch rounded bg-teal-700 hover:bg-teal-600 text-white font-semibold"
      >
        {showTrace ? "Hide the explanation" : "Why is the air bad here?"}
      </button>
      {showTrace && <AgentTrace explain={explain} />}
      {showTrace && explain.data && <CausesPanel attribution={explain.data.attribution} />}
      {showTrace && explain.data && <PersonaCards advice={explain.data.advice} />}
      <p className="text-xs text-slate-400">
        Nearest official station:{" "}
        {stations.data?.[0]
          ? `${stations.data[0].name} — ${stations.data[0].pm25?.toFixed(0)} µg/m³`
          : "…"}
      </p>
    </div>
  );

  return (
    <div className="relative h-[calc(100dvh-3.5rem)] md:h-[calc(100dvh-3.5rem)] flex flex-col md:flex-row">
      <div className="absolute inset-0 md:relative md:flex-1 md:order-1">
        <SourceMap
          lat={point.lat}
          lon={point.lon}
          sources={sources.data?.sources ?? []}
          onPick={selectPlace}
        />
      </div>

      {isDesktop ? (
        <aside
          data-testid="desktop-panel"
          className="hidden md:flex md:order-2 w-[26rem] lg:w-[32rem] shrink-0 flex-col overflow-y-auto border-l border-white/10 p-4 gap-4"
        >
          <SearchBox onSelect={selectPlace} />
          {panel}
        </aside>
      ) : (
        <div className="md:hidden absolute inset-x-0 bottom-0 z-20">
          <BottomSheet
            full={false}
            peek={
              <div className="p-4">
                <EstimatePanel
                  estimate={estimate.data}
                  loading={estimate.isPending}
                  error={estimate.error}
                  compact
                />
              </div>
            }
          >
            <div className="p-4 space-y-4">
              <SearchBox onSelect={selectPlace} />
              {panel}
            </div>
          </BottomSheet>
        </div>
      )}
    </div>
  );
}

export default Explorer;

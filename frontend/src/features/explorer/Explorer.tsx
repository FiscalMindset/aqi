import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { SourceMap } from "./SourceMap";
import { BottomSheet } from "../../components/BottomSheet";
import { SearchBox } from "./SearchBox";
import { EstimatePanel } from "./EstimatePanel";
import { FeatureBreakdown } from "./FeatureBreakdown";
import { ModelCardPanel } from "./ModelCardPanel";
import { CausesPanel } from "./CausesPanel";
import { PersonaCards } from "./PersonaCards";
import { AgentTrace } from "./AgentTrace";
import { ExplanationPanel } from "./ExplanationPanel";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import {
  useEstimate,
  useExplain,
  useModelCard,
  useSources,
  useStations,
} from "../../hooks/useApi";

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
  const modelCard = useModelCard();

  function selectPlace(lat: number, lon: number) {
    setPoint({ lat, lon });
    navigate(`/place/${lat}/${lon}`, { replace: true });
  }

  const panel = (
    <div className="space-y-4">
      <EstimatePanel estimate={estimate.data} loading={estimate.isPending} error={estimate.error} />
      {estimate.data && (
        <FeatureBreakdown
          features={estimate.data.features_used}
          anchor={estimate.data.persistence_anchor_ugm3}
          adjustment={estimate.data.model_adjustment_ugm3}
          finalValue={estimate.data.pm25_mid}
        />
      )}
      <button
        type="button"
        data-testid="explain-toggle"
        aria-expanded={showTrace}
        onClick={() => setShowTrace((v) => !v)}
        className="w-full min-h-touch rounded bg-teal-700 hover:bg-teal-600 text-white font-semibold"
      >
        {showTrace ? "Hide the explanation" : "Why is the air bad here?"}
      </button>
      {showTrace && explain.data && (
        <ExplanationPanel
          headline={explain.data.headline}
          paragraphs={explain.data.paragraphs}
          passages={explain.data.passages}
          gaps={explain.data.evidence_gaps}
          servedBy={explain.data.prose_served_by}
        />
      )}
      {showTrace && <AgentTrace explain={explain} />}
      {showTrace && explain.data && <CausesPanel attribution={explain.data.attribution} />}
      {showTrace && explain.data && <PersonaCards advice={explain.data.advice} />}
      <ModelCardPanel card={modelCard.data ?? null} />
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
      <div className="absolute inset-0 min-h-[45dvh] md:relative md:min-h-0 md:flex-1 md:order-1">
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
          className="hidden md:flex md:order-2 w-[24rem] lg:w-[30rem] xl:w-[34rem] shrink-0 flex-col overflow-y-auto overscroll-contain border-l border-white/10 bg-slate-950/40 px-4 py-4 gap-4"
        >
          <SearchBox onSelect={selectPlace} />
          {panel}
        </aside>
      ) : (
        <div className="md:hidden absolute inset-x-0 bottom-0 z-20 max-h-[55dvh] overflow-y-auto overscroll-contain">
          <BottomSheet
            full={false}
            peek={
              <div className="space-y-3 p-4">
                <EstimatePanel
                  estimate={estimate.data}
                  loading={estimate.isPending}
                  error={estimate.error}
                  compact
                />
                {estimate.data && estimate.data.features_used.length > 0 && (
                  <FeatureBreakdown
                    features={estimate.data.features_used.slice(0, 3)}
                    anchor={estimate.data.persistence_anchor_ugm3}
                    adjustment={estimate.data.model_adjustment_ugm3}
                    finalValue={estimate.data.pm25_mid}
                  />
                )}
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

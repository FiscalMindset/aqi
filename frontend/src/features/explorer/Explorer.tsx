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
import { WindPanel } from "./WindPanel";
import { TrainingDataPanel } from "../methodology/TrainingDataPanel";
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
  // The explanation is the product, not a debug view: it loads with the
  // estimate and is shown by default. The toggle now collapses the supporting
  // detail (agent trace, causes, persona advice) for people who want just the
  // number.
  const [showDetail, setShowDetail] = useState(false);

  const estimate = useEstimate(point.lat, point.lon);
  const stations = useStations(point.lat, point.lon);
  const sources = useSources(point.lat, point.lon);
  const explain = useExplain(point.lat, point.lon);
  const modelCard = useModelCard();

  function selectPlace(lat: number, lon: number) {
    setPoint({ lat, lon });
    navigate(`/place/${lat}/${lon}`, { replace: true });
  }

  const panel = (
    <div className="space-y-4">
      <EstimatePanel estimate={estimate.data} loading={estimate.isPending} error={estimate.error} />
      {estimate.data?.weather && <WindPanel weather={estimate.data.weather} />}
      {estimate.data && (
        <FeatureBreakdown
          features={estimate.data.features_used}
          anchor={estimate.data.persistence_anchor_ugm3}
          adjustment={estimate.data.model_adjustment_ugm3}
          finalValue={estimate.data.pm25_mid}
        />
      )}
      {explain.isPending && (
        <p className="text-sm text-muted" role="status" data-testid="explain-loading">
          Working out what is causing this…
        </p>
      )}
      {explain.isError && (
        <p className="text-sm text-amber-300" role="alert" data-testid="explain-error">
          The explanation could not be produced. The estimate above is still
          valid.
        </p>
      )}
      {explain.data && (
        <ExplanationPanel
          headline={explain.data.headline}
          paragraphs={explain.data.paragraphs}
          passages={explain.data.passages}
          gaps={explain.data.evidence_gaps}
          servedBy={explain.data.prose_served_by}
        />
      )}
      <button
        type="button"
        data-testid="explain-toggle"
        aria-expanded={showDetail}
        onClick={() => setShowDetail((v) => !v)}
        className="w-full min-h-touch rounded border border-line px-3 py-2 text-sm font-semibold"
      >
        {showDetail ? "Hide the supporting detail" : "Show the supporting detail"}
      </button>
      {showDetail && <AgentTrace explain={explain} />}
      {showDetail && explain.data && <CausesPanel attribution={explain.data.attribution} />}
      {showDetail && explain.data && <PersonaCards advice={explain.data.advice} />}
      <ModelCardPanel card={modelCard.data ?? null} />
      <TrainingDataPanel />
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
      {/* The map wrapper must have a resolvable height on every breakpoint.
          `absolute inset-0` gives the div a definite box only when the nearest
          positioned ancestor does; combined with `min-h-[45dvh]` on the same
          element, `h-full` inside it resolved against an auto height and the
          canvas collapsed to zero. On mobile the map now owns 45dvh outright,
          and on desktop it is a flex child with `min-h-0` so it cannot grow
          past the row. */}
      <div className="relative h-[45dvh] shrink-0 md:relative md:h-auto md:min-h-0 md:flex-1 md:order-1">
        <SourceMap
          lat={point.lat}
          lon={point.lon}
          sources={sources.data?.sources ?? []}
          stations={stations.data ?? []}
          windFromDeg={estimate.data?.weather?.wind_from_deg ?? null}
          onPick={selectPlace}
        />
      </div>

      {isDesktop ? (
        <aside
          data-testid="desktop-panel"
          className="hidden md:flex md:order-2 w-[24rem] lg:w-[30rem] xl:w-[34rem] shrink-0 flex-col overflow-y-auto overscroll-contain border-l border-white/10 bg-slate-950/40 px-4 py-4 gap-4"
        >
          <div className="sticky top-0 z-20 -mx-4 bg-slate-950/95 px-4 pb-2 pt-1 backdrop-blur">
            <SearchBox onSelect={selectPlace} />
          </div>
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
              <div className="sticky top-0 z-20 -mx-4 bg-night-800/95 px-4 pb-2 backdrop-blur">
                <SearchBox onSelect={selectPlace} />
              </div>
              {panel}
            </div>
          </BottomSheet>
        </div>
      )}
    </div>
  );
}

export default Explorer;

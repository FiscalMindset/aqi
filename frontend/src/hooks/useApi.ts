import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  api,
  type Estimate,
  type ModelCard,
  type ModelVersions,
  type TrainingData,
  type RouteComparison,
  type SourcesResponse,
  type StationReading,
  type StatusResponse,
  type ValidationMetrics,
} from "../lib/api";

export function useEstimate(
  lat: number,
  lon: number,
): UseQueryResult<Estimate, Error> {
  return useQuery({
    queryKey: ["estimate", lat, lon],
    queryFn: () => api.estimate(lat, lon),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

export function useStations(
  lat: number,
  lon: number,
): UseQueryResult<StationReading[], Error> {
  return useQuery({
    queryKey: ["stations", lat, lon],
    queryFn: () => api.stations(lat, lon),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

export function useSources(
  lat: number,
  lon: number,
): UseQueryResult<SourcesResponse, Error> {
  return useQuery({
    queryKey: ["sources", lat, lon],
    queryFn: () => api.sources(lat, lon),
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });
}

/**
 * Always fetches. The explanation is the product, not a debug view, so it loads
 * with the estimate rather than behind a click; the caller decides only whether
 * to show the supporting detail.
 */
export function useExplain(lat: number, lon: number) {
  return useQuery({
    queryKey: ["explain", lat, lon],
    queryFn: () => api.explain(lat, lon),
    staleTime: 5 * 60_000,
  });
}

export function useRouteCompare(
  from: { lat: number; lon: number; name: string } | null,
  to: { lat: number; lon: number; name: string } | null,
): UseQueryResult<RouteComparison, Error> {
  return useQuery({
    queryKey: ["route-compare", from, to],
    queryFn: () =>
      api.compareRoutes({
        fromLat: from!.lat,
        fromLon: from!.lon,
        toLat: to!.lat,
        toLon: to!.lon,
        maxSamples: 10,
      }),
    // Both endpoints must exist AND carry finite coordinates. `Boolean(from &&
    // to)` was true for a Place object whose lat/lon were undefined, so the
    // request went out with missing fields, came back 422, and - because the
    // gateway base64-encodes problem bodies - the reader saw a JSON parse error
    // instead of "one or more fields are missing".
    enabled: Boolean(
      from &&
        to &&
        Number.isFinite(from.lat) &&
        Number.isFinite(from.lon) &&
        Number.isFinite(to.lat) &&
        Number.isFinite(to.lon),
    ),
    // routing + exposure profiling is expensive; a route does not change by the second
    staleTime: 5 * 60 * 1000,
  });
}

export function useModelCard(): UseQueryResult<ModelCard, Error> {
  return useQuery({
    queryKey: ["model-card"],
    queryFn: api.model,
    staleTime: 60 * 60 * 1000,
  });
}

export function useTrainingData(): UseQueryResult<TrainingData, Error> {
  return useQuery({
    queryKey: ["training-data"],
    queryFn: api.trainingData,
    staleTime: 60 * 60 * 1000,
  });
}

export function useModelVersions(): UseQueryResult<ModelVersions, Error> {
  return useQuery({
    queryKey: ["model-versions"],
    queryFn: api.modelVersions,
    staleTime: 60 * 60 * 1000,
  });
}

export function useValidation(): UseQueryResult<ValidationMetrics, Error> {
  return useQuery({
    queryKey: ["validation"],
    queryFn: () => api.validation(),
    staleTime: 30 * 60 * 1000,
  });
}

export function useStatus(): UseQueryResult<StatusResponse, Error> {
  return useQuery({
    queryKey: ["status"],
    queryFn: () => api.status(),
    refetchInterval: 60_000,
  });
}

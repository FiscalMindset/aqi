import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { api, type Estimate, type ExplainResponse, type SourcesResponse, type StationReading, type StatusResponse, type ValidationMetrics } from "../lib/api";

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

export function useExplain(
  lat: number,
  lon: number,
  enabled: boolean,
): UseQueryResult<ExplainResponse, Error> {
  return useQuery({
    queryKey: ["explain", lat, lon],
    queryFn: () => api.explain(lat, lon),
    enabled,
    staleTime: 5 * 60 * 1000,
    retry: 1,
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

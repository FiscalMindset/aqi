/**
 * Typed API client for the Dhuan Detective API.
 *
 * Rules honoured here: errors are `application/problem+json`; the client
 * surfaces them as typed errors; `X-Dhuan-Demo` flips the demo banner;
 * timeouts mirror the backend defaults.
 */

/**
 * Same-origin `/v1` by default: the web app is served behind CloudFront,
 * which routes `/v1/*` to the API origin (see infra/template.yaml). `vite
 * dev` proxies `/v1` to the local backend (vite.config.ts).
 */
export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "/v1";

export interface Problem {
  type: string;
  title: string;
  status: number;
  detail?: string;
  correlation_id?: string;
  errors?: Array<{ field: string; issue: string; message: string }>;
}

export class ApiError extends Error {
  constructor(
    readonly problem: Problem,
    readonly status: number,
  ) {
    super(problem.detail ?? problem.title);
    this.name = "ApiError";
  }
}

export interface StationReading {
  station_id: string;
  name: string;
  latitude: number;
  longitude: number;
  provider: string;
  distance_km: number;
  pm25: number | null;
  observed_at: string | null;
  age_seconds: number | null;
  category: string | null;
}

export interface Estimate {
  lat: number;
  lon: number;
  ts_utc: string;
  pm25_low: number;
  pm25_mid: number;
  pm25_high: number;
  category: string;
  nearest_station_pm25: number | null;
  nearest_station_name: string | null;
  data_age_seconds: number;
  stale: boolean;
  model_version: string;
  served_by: string;
  cpcb_table_version: string;
  honesty: string;
  demo_mode: boolean;
}

export interface SourceHit {
  osm_id: string;
  type: string;
  name: string;
  latitude: number;
  longitude: number;
  distance_km: number;
  bearing_deg: number;
  in_upwind_cone: boolean;
  influence_score: number;
  area_m2: number | null;
  attribution: string;
}

export interface SourcesResponse {
  query: Record<string, unknown>;
  wind_from_deg: number | null;
  count: number;
  sources: SourceHit[];
  openness_note: string;
}

export interface EvidenceItem {
  evidence_id: string;
  tool: string;
  args: Record<string, unknown>;
  summary: string;
  fetched_at: string;
  ok: boolean;
  note?: string | null;
}

export interface LikelyCause {
  rank: number;
  category: string;
  label: string;
  band: "High" | "Medium" | "Low";
  evidence_ids: string[];
  reasoning: string;
  distance_km?: number | null;
  bearing_deg?: number | null;
}

export interface Attribution {
  summary: string;
  likely_causes: LikelyCause[];
  confidence: "high" | "medium" | "low";
  confidence_reason: string;
  evidence: EvidenceItem[];
  tool_calls: string[];
  demo_mode: boolean;
}

export interface Advice {
  persona: string;
  headline: string;
  actions: string[];
  evidence_ids: string[];
  disclaimer: string;
}

export interface ExplainResponse {
  lat: number;
  lon: number;
  served_by: string;
  attribution: Attribution;
  advice: Advice[];
  demo_mode: boolean;
  note: string;
}

export interface ValidationMetrics {
  version: string;
  created_utc: string;
  n_rows: number;
  temporal_holdout: Record<string, number>;
  loso_mean: Record<string, number>;
  baselines: Record<string, Record<string, number>>;
  winner: string;
  interval_coverage_note: string;
}

export interface StatusResponse {
  status: "ok" | "degraded";
  api_version: string;
  model_version: string;
  feeds: Array<{
    feed: string;
    ok: boolean;
    last_success_at: string | null;
    age_seconds: number | null;
    last_error: string | null;
    records_last_run: number;
  }>;
  coverage: Record<string, unknown>;
  demo_mode: boolean;
}

function markDemo(res: Response): void {
  if (res.headers.get("x-dhuan-demo") === "1") {
    document.documentElement.dataset.demo = "1";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal });
    markDemo(res);
    if (res.status === 204) return undefined as T;
    const contentType = res.headers.get("content-type") ?? "";
    if (!res.ok) {
      if (contentType.includes("application/problem+json")) {
        const problem = (await res.json()) as Problem;
        throw new ApiError(problem, res.status);
      }
      throw new ApiError(
        { type: "about:blank", title: res.statusText, status: res.status },
        res.status,
      );
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timeout);
  }
}

export const api = {
  estimate: (lat: number, lon: number) =>
    request<Estimate>(`/estimate?lat=${lat}&lon=${lon}`),
  stations: (lat: number, lon: number, limit = 10) =>
    request<StationReading[]>(`/stations?lat=${lat}&lon=${lon}&limit=${limit}`),
  sources: (lat: number, lon: number, radiusKm = 15, upwind = true) =>
    request<SourcesResponse>(
      `/sources?lat=${lat}&lon=${lon}&radius_km=${radiusKm}&upwind=${upwind}`,
    ),
  explain: (lat: number, lon: number) =>
    request<ExplainResponse>("/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat, lon }),
    }),
  validation: () => request<ValidationMetrics>("/validation"),
  status: () => request<StatusResponse>("/status"),
  subscribe: (body: {
    email: string;
    locality: string;
    lat: number;
    lon: number;
    threshold_category: string;
  }) =>
    request<{ id: string; status: string; locality?: string }>("/subscriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};

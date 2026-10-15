/**
 * Typed API client for the Dhuan Detective API.
 *
 * Rules honoured here: errors are `application/problem+json`; the client
 * surfaces them as typed errors;
 * timeouts mirror the backend defaults.
 */

/**
 * The API lives under the same prefix the app is served from.
 *
 * A hardcoded "/v1" looks harmless because it is same-origin, but on AWS the
 * app is mounted at `/staging/`, so `/v1/estimate` resolves to the gateway
 * root, which serves no API and returns 403. Every request failed with
 * "Could not load the estimate" while the backend was perfectly healthy at
 * `/staging/v1/estimate`.
 *
 * BASE_PATH comes from Vite's `base` option, which the Dockerfile sets from
 * the same build arg as VITE_BASE_PATH, so the two cannot drift.
 */
const BASE_PATH = import.meta.env.BASE_URL ?? "/";

export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  `${BASE_PATH.replace(/\/$/, "")}/v1`;

/** Abort budget for a single indexed read. See `request` for the exceptions. */
const DEFAULT_TIMEOUT_MS = 15000;
/**
 * Routing plus per-corridor exposure profiling. Kept just under the API
 * Gateway integration timeout (29s) so the browser gives up a moment before
 * the gateway does, and gets a real error instead of a stalled page.
 */
const ROUTE_TIMEOUT_MS = 27000;

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

export interface ModelVersion {
  version_id: string;
  trained_utc: string;
  n_rows: number;
  n_stations: number | null;
  snapshot_sha256: string;
  conformal_radius_ugm3: number | null;
  temporal_mae: number | null;
  temporal_rmse: number | null;
  temporal_r2: number | null;
  unseen_mae: number | null;
  baseline_mae: number | null;
  git_commit: string | null;
  artifact_present: boolean;
}

export interface ModelVersions {
  current: string | null;
  versions: ModelVersion[];
}

export interface CrossCheck {
  pm25_ugm3: number | null;
  us_aqi: number | null;
  european_aqi: number | null;
  dust_ugm3: number | null;
  delta_ugm3: number | null;
  age_seconds: number | null;
  provider: string;
  is_ground_reading: boolean;
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

export interface Weather {
  wind_speed_ms: number | null;
  wind_gust_ms: number | null;
  wind_from_deg: number | null;
  wind_from_label: string | null;
  temperature_c: number | null;
  relative_humidity_pct: number | null;
  precipitation_mm: number | null;
  age_seconds: number | null;
  stale: boolean;
  /** Derived from wind speed, never a measurement. */
  ventilation: string | null;
  ventilation_reason: string | null;
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
  /** The nearest station's value 1h ago: the baseline the model corrects. */
  persistence_anchor_ugm3: number | null;
  /** What the model added/subtracted from that baseline. */
  model_adjustment_ugm3: number | null;
  /** How this number was produced. */
  method: string;
  /** Per-parameter effect on this particular estimate, in ug/m3. */
  features_used: FeatureContribution[];
  /** Current conditions at this point; null only if the weather feed failed. */
  weather: Weather | null;
  cross_check: CrossCheck | null;
}

export interface FeatureContribution {
  name: string;
  value: number;
  unit: string;
  reference: number;
  contribution_ugm3: number;
  absolute_effect_ugm3: number;
}

export interface ModelMetrics {
  n_train: number;
  n_test: number;
  mae: number;
  rmse: number;
  r2: number;
  bias: number;
  coverage80: number | null;
  mean_width: number | null;
}

export interface ModelCard {
  algorithm: string;
  trained_at_utc: string;
  snapshot_sha256: string;
  n_rows: number;
  stations: { location_id: number; rows: number }[];
  temporal_holdout: ModelMetrics;
  leave_one_station_out: ModelMetrics;
  baselines: Record<string, ModelMetrics>;
  winner: string;
  features: string[];
  n_features: number;
  conformal_radius_ugm3: number;
  notes: string[];
}

export interface RouteSample {
  lat: number;
  lon: number;
  pm25_mid: number | null;
  category: string | null;
  data_age_seconds: number | null;
  served_by: string | null;
}

export interface RouteCorridor {
  rank: number;
  kind: "road" | "straight-line";
  distance_km: number;
  duration_min: number;
  mean_pm25: number;
  peak_pm25: number;
  peak_at: { lat: number; lon: number };
  dose_index: number | null;
  served_points: number;
  geometry: [number, number][];
  samples: RouteSample[];
}

export interface RouteComparison {
  origin: { lat: number; lon: number };
  destination: { lat: number; lon: number };
  router: string;
  corridor_count: number;
  /** Every corridor, cleanest first. */
  corridors: RouteCorridor[];
  cleanest: RouteCorridor;
  worst: RouteCorridor;
  mean_pm25_saving: number;
  samples_per_corridor: number;
  note: string;
  honesty_note: string;
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

/** One grounded sentence-group and the evidence passages it came from. */
export interface ExplanationParagraph {
  intent: string;
  text: string;
  passage_ids: string[];
}

export interface Passage {
  passage_id: string;
  kind: string;
  text: string;
  authority: number;
  measured: boolean;
  observed_at: string | null;
  age_seconds: number | null;
  source_url: string | null;
  evidence_id: string | null;
  facts: Record<string, unknown>;
}

export interface RetrievalTraceEntry {
  passage_id: string;
  kind: string;
  score: number;
  reasons: string[];
}

export interface Attribution {
  summary: string;
  likely_causes: LikelyCause[];
  confidence: "high" | "medium" | "low";
  confidence_reason: string;
  evidence: EvidenceItem[];
  tool_calls: string[];
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
  /** Which layer wrote the prose: the deterministic composer, or Groq on top. */
  prose_served_by: string;
  attribution: Attribution;
  headline: string;
  explanation: string;
  paragraphs: ExplanationParagraph[];
  passages: Passage[];
  retrieval_trace: RetrievalTraceEntry[];
  /** Inputs that failed to answer; the explanation says so rather than guessing. */
  evidence_gaps: string[];
  advice: Advice[];
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

export interface CoverageBlock {
  bbox: { min_lat: number; min_lon: number; max_lat: number; max_lon: number };
  boundary_source: string;
  boundary_fetched: string;
  boundary_license: string;
}

export interface TrainingData {
  available: boolean;
  reason?: string;
  station_observations: number;
  weather_observations: number;
  stations: number;
  busiest_station_rows: number;
  median_station_rows: number;
  first_observation: string;
  last_observation: string;
  observed_min_ugm3: number;
  observed_max_ugm3: number;
  observed_mean_ugm3: number;
  feature_count: number;
  features: string[];
  sources?: Record<string, string>;
  metrics: {
    version?: string;
    created_utc?: string;
    n_rows?: number;
    winner?: string;
    temporal_holdout?: Record<string, number>;
    loso_mean?: Record<string, number>;
    baselines?: Record<string, Record<string, number>>;
  };
}

export interface ReadyCheck {
  component: string;
  ok: boolean;
  detail: string;
}

export interface ReadyResponse {
  status: "ready" | "degraded";
  checks: ReadyCheck[];
  integrations: Record<string, string | boolean>;
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
  /** Which credential path each optional dependency resolved to. */
  integrations: Record<string, string | boolean>;
  coverage: CoverageBlock;
}

async function requestAt<T>(
  path: string,
  init?: RequestInit,
  options: { tolerateStatuses?: number[]; timeoutMs?: number } = {},
): Promise<T> {
  const base = (import.meta.env.BASE_URL ?? "/").replace(/\/$/, "");
  return request<T>(path, init, base, options);
}

async function request<T>(
  path: string,
  init?: RequestInit,
  base: string = API_BASE,
  options: { tolerateStatuses?: number[]; timeoutMs?: number } = {},
): Promise<T> {
  const controller = new AbortController();
  // Most calls are a single indexed lookup and answer in well under a second.
  // Route comparison is different: it calls the routing service and then runs
  // the estimator along every corridor, and on a cold Lambda that legitimately
  // runs past the default. Aborting at 15s left the page stuck on "Finding
  // real routes" with no result and no error, which is the worst of both.
  const timeout = setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  );
  try {
    const res = await fetch(`${base}${path}`, { ...init, signal: controller.signal });
    if (res.status === 204) return undefined as T;
    const contentType = res.headers.get("content-type") ?? "";
    if (!res.ok && !(options.tolerateStatuses ?? []).includes(res.status)) {
      if (contentType.includes("application/problem+json")) {
        const problem = await readJson<Problem>(res);
        throw new ApiError(problem, res.status);
      }
      throw new ApiError(
        { type: "about:blank", title: res.statusText, status: res.status },
        res.status,
      );
    }
    return readJson<T>(res);
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Read a JSON body, tolerating a base64-wrapped one.
 *
 * API Gateway in front of this service returns successful responses as plain
 * JSON but base64-encodes problem responses, even though the template sets
 * BinaryMediaTypes to a catch-all expecting verbatim passthrough. res.json() therefore
 * threw a parse error and the reader saw that instead of the actual API
 * problem, which is the one thing worth showing.
 *
 * Tries plain JSON first, then base64. If neither parses, the raw text is
 * surfaced rather than swallowed.
 */
async function readJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  try {
    return JSON.parse(text) as T;
  } catch {
    // fall through to the base64 attempt
  }
  const trimmed = text.trim();
  if (/^[A-Za-z0-9+/]+={0,2}$/.test(trimmed) && trimmed.length > 16) {
    try {
      const decoded = atob(trimmed);
      return JSON.parse(decoded) as T;
    } catch {
      // fall through to the error below
    }
  }
  throw new ApiError(
    {
      type: "about:blank",
      title: "Unreadable response",
      status: res.status,
      detail: text.slice(0, 200),
    },
    res.status,
  );
}

export const api = {
  /** Dependency probes: what the estimate actually needs, not just liveness. */
  // /ready lives at the site root, not under /v1, so it must not go through
  // API_BASE. It answers 503 when a dependency is degraded, which is a valid,
  // informative answer rather than a transport failure - so this one request
  // deliberately does not throw on 5xx, or a degraded system would blank the
  // very page that reports it.
  ready: () => requestAt<ReadyResponse>("/ready", undefined, { tolerateStatuses: [503] }),
  /** Counts derived from the training snapshot shipped in the image. */
  trainingData: () => request<TrainingData>("/training-data"),
  /** Render the real alert email for a point without sending it. */
  previewAlert: (body: {
    lat: number;
    lon: number;
    locality?: string;
    threshold_category?: string;
  }) => request<{ subject: string; body: string; html: string }>("/alerts/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }),
  // explain=true asks the API for the per-parameter breakdown. It costs one
  // extra batched model pass, so it is opt-in rather than always on.
  estimate: (lat: number, lon: number, explain = true) =>
    request<Estimate>(`/estimate?lat=${lat}&lon=${lon}&explain=${explain}`),
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
  compareRoutes: (body: {
    fromLat: number;
    fromLon: number;
    toLat: number;
    toLon: number;
    maxSamples?: number;
  }) =>
    request<RouteComparison>(
      "/routes/compare",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          from_lat: body.fromLat,
          from_lon: body.fromLon,
          to_lat: body.toLat,
          to_lon: body.toLon,
          max_samples: body.maxSamples ?? 10,
        }),
      },
      API_BASE,
      { timeoutMs: ROUTE_TIMEOUT_MS },
    ),
  model: () => request<ModelCard>("/model"),
  modelVersions: () => request<ModelVersions>("/model/versions"),
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

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "../../src/i18n";
import { Methodology } from "../../src/features/methodology/Methodology";
import { StatusPage } from "../../src/features/status/StatusPage";
import { HowItWorks } from "../../src/features/howitworks/HowItWorks";
import * as apiLib from "../../src/lib/api";

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={client}>
        <MemoryRouter>{ui}</MemoryRouter>
      </QueryClientProvider>
    </I18nextProvider>,
  );
}

beforeEach(() => vi.restoreAllMocks());

describe("Methodology", () => {
  it("renders live validation metrics and the shipped winner", async () => {
    vi.spyOn(apiLib.api, "validation").mockResolvedValue({
      version: "eval-1",
      created_utc: "2026-10-10T00:00:00Z",
      n_rows: 22106,
      temporal_holdout: { mae: 26.1, rmse: 59.8, r2: 0.63, bias: -18.3 },
      loso_mean: { mae: 131.6 },
      baselines: {
        "persistence-lag1h": { mae: 24.9 },
        "global-mean": { mae: 250.8 },
      },
      winner: "nearest-station-baseline (persistence-lag1h)",
      interval_coverage_note: "conformal radius (80% target): 28.65; coverage: 0.800",
    });
    wrap(<Methodology />);
    await waitFor(() =>
      expect(screen.getByTestId("val-mae").textContent).toBe("26.1"),
    );
    expect(screen.getByTestId("winner").textContent).toContain(
      "nearest-station-baseline",
    );
    // honest limitations are always listed
    expect(screen.getAllByText(/24-hour averages/).length).toBeGreaterThan(0);
  });
});

describe("StatusPage", () => {
  it("renders feed freshness", async () => {
    vi.spyOn(apiLib.api, "status").mockResolvedValue({
      status: "degraded",
      api_version: "0.1.0",
      model_version: "baseline-v1",
      feeds: [
        {
          feed: "openaq",
          ok: true,
          last_success_at: "2026-10-10T12:00:00Z",
          age_seconds: 600,
          last_error: null,
          records_last_run: 3,
        },
      ],
      coverage: {
      bbox: { min_lat: 28.4, min_lon: 76.8, max_lat: 28.9, max_lon: 77.4 },
      boundary_source: "OpenStreetMap via Overpass API",
      boundary_fetched: "2026-10-12T00:00:00Z",
      boundary_license: "ODbL 1.0",
    },
    integrations: { stations: "openaq-public-archive" },
    });
    wrap(<StatusPage />);
    await waitFor(() => expect(screen.getByTestId("overall")).toBeDefined());
    expect(screen.getByTestId("overall").textContent).toContain("degraded");
    expect(screen.getByText("openaq")).toBeDefined();
  });
});

describe("HowItWorks", () => {
  it("walks through steps", async () => {
    vi.spyOn(apiLib.api, "explain").mockResolvedValue({
      lat: 28.6139,
      lon: 77.209,
      served_by: "scripted-deterministic",
    prose_served_by: "composed-grounded",
    headline: "Estimated 200 µg/m³ here — Very Poor band.",
    explanation: "We estimate 200 µg/m³ at this point.",
    paragraphs: [{ intent: "what we estimate here", text: "We estimate 200 µg/m³.", passage_ids: ["model-estimate"] }],
    passages: [
      {
        passage_id: "model-estimate",
        kind: "model_estimate",
        text: "Our estimate is 200 ug/m3",
        authority: 0.86,
        measured: false,
        observed_at: null,
        age_seconds: null,
        source_url: null,
        evidence_id: null,
        facts: {},
      },
    ],
    retrieval_trace: [],
    evidence_gaps: [],
      attribution: {
        summary: "",
        likely_causes: [],
        confidence: "medium",
        confidence_reason: "",
        evidence: [
          {
            evidence_id: "ev_1",
            tool: "get_air_and_wind",
            args: {},
            summary: "wind 3 m/s from 292",
            fetched_at: "2026-10-10T12:00:00Z",
            ok: true,
          },
        ],
        tool_calls: [],
      },
      advice: [],
      note: "",
    });
    wrap(<HowItWorks />);
    expect(screen.getByTestId("how-it-works")).toBeDefined();
    const next = screen.getByRole("button", { name: /next/i });
    next.click();
    next.click();
    await waitFor(() => expect(screen.getByText(/get_air_and_wind/)).toBeDefined());
  });
});

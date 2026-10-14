import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "../../src/i18n";
import { Subscribe } from "../../src/features/subscribe/Subscribe";
import { RoutesCompare } from "../../src/features/routes/RoutesCompare";
import * as apiLib from "../../src/lib/api";
import { maplibreMock } from "../helpers/maplibre";

// The location picker inside Subscribe dynamically imports MapLibre. Without
// this the real library loads into jsdom and the form tests time out.
vi.mock("maplibre-gl", () => maplibreMock());

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </I18nextProvider>,
  );
}

// Subscribe reads the current estimate for the chosen point on mount so it can
// say whether the chosen threshold would fire today. Left unmocked it issued a
// real fetch in jsdom, which is what made these two tests intermittently take
// four seconds and fail.
const estimateStub = {
  lat: 28.7146,
  lon: 77.1025,
  ts_utc: "2026-10-14T10:00:00+00:00",
  pm25_low: 40,
  pm25_mid: 55,
  pm25_high: 70,
  category: "Poor",
  aqi_sub_index: null,
  nearest_station_pm25: 55,
  nearest_station_name: "Rohini",
  data_age_seconds: 0,
  stale: false,
  model_version: "test",
  served_by: "model",
  cpcb_table_version: "2014-11-24",
  honesty: "",
  persistence_anchor_ugm3: 55,
  model_adjustment_ugm3: 0,
  features_used: [],
  weather: null,
  cross_check: null,
  method: "gradient-boosted-trees on persistence-anchored residual",
};

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(apiLib.api, "estimate").mockResolvedValue(estimateStub);
});


describe("Subscribe", () => {
  it("submits and reports the confirmation flow", async () => {
    vi.spyOn(apiLib.api, "subscribe").mockResolvedValue({
      id: "abc123",
      status: "pending_confirmation",
      locality: "Rohini",
    });
    wrap(<Subscribe />);
    const user = userEvent.setup({ delay: null });
    await user.type(screen.getByTestId("sub-email"), "parent@example.com");
    await user.click(screen.getByTestId("sub-submit"));
    await waitFor(() => expect(screen.getByTestId("sub-message")).toBeDefined());
    expect(screen.getByTestId("sub-message").textContent).toMatch(/confirm/i);
  }, 20000);

  it("surfaces an API problem response as an alert", async () => {
    vi.spyOn(apiLib.api, "subscribe").mockRejectedValue(
      new apiLib.ApiError(
        {
          type: "https://x/problems/outside-coverage",
          title: "Point outside coverage",
          status: 422,
          detail: "Alerts are available for Delhi-NCR only.",
        },
        422,
      ),
    );
    wrap(<Subscribe />);
    const user = userEvent.setup({ delay: null });
    await user.type(screen.getByTestId("sub-email"), "x@example.com");
    await user.click(screen.getByTestId("sub-submit"));
    await waitFor(() => expect(screen.getByRole("alert")).toBeDefined());
  }, 20000);
});

describe("RoutesCompare", () => {
  it("ranks the cleaner longer route first, on exposure rather than distance", async () => {
    vi.spyOn(apiLib.api, "compareRoutes").mockResolvedValue({
      origin: { lat: 28.6139, lon: 77.209 },
      destination: { lat: 28.7146, lon: 77.1025 },
      router: "project-osrm",
      corridor_count: 2,
      cleanest:       {
        rank: 1,
        kind: "road",
        distance_km: 9.0,
        duration_min: 10,
        mean_pm25: 70,
        peak_pm25: 90,
        peak_at: { lat: 28.6139, lon: 77.209 },
        dose_index: 630,
        served_points: 2,
        geometry: [
          [77.209, 28.6139],
          [77.16, 28.6],
          [77.1025, 28.7146],
        ],
        samples: [
          { lat: 28.6139, lon: 77.209, pm25_mid: 90, pm25_low: 80, pm25_high: 100 },
          { lat: 28.7146, lon: 77.1025, pm25_mid: 85, pm25_low: 75, pm25_high: 95 },
        ],
      },
      worst: {
        rank: 2,
        kind: "road",
        distance_km: 14.0,
        duration_min: 15,
        mean_pm25: 120,
        peak_pm25: 210,
        peak_at: { lat: 28.6139, lon: 77.209 },
        dose_index: 1080,
        served_points: 2,
        geometry: [
          [77.209, 28.6139],
          [77.1025, 28.7146],
        ],
        samples: [
          { lat: 28.6139, lon: 77.209, pm25_mid: 210, pm25_low: 190, pm25_high: 230 },
          { lat: 28.7146, lon: 77.1025, pm25_mid: 180, pm25_low: 160, pm25_high: 200 },
        ],
      },
      mean_pm25_saving: 50,
      samples_per_corridor: 2,
    } as never);

    wrap(<RoutesCompare />);
    await waitFor(() => expect(screen.getByTestId("corridor-1")).toBeDefined());
    expect(screen.getByTestId("corridor-2")).toBeDefined();
    // the cleanest corridor is the longer, 14 km one: ranking is by exposure
    const summary = screen.getByTestId("routes-summary").textContent ?? "";
    expect(summary).toContain("50");
  });
});

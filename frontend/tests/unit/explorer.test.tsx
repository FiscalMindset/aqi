import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "../../src/i18n";
import * as apiLib from "../../src/lib/api";

// MapLibre needs WebGL; mock it for jsdom (the real map renders in e2e)
vi.mock("maplibre-gl", () => {
  class FakeMap {
    addControl() {}
    on() {}
    flyTo() {}
    remove() {}
    getZoom() {
      return 12;
    }
    getSource() {
      return undefined;
    }
    addSource() {}
    addLayer() {}
    isStyleLoaded() {
      return false;
    }
  }
  return {
    default: { Map: FakeMap, NavigationControl: class {} },
    Map: FakeMap,
    NavigationControl: class {},
  };
});

import { Explorer } from "../../src/features/explorer/Explorer";

function wrap(route = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  window.history.pushState({}, "", route);
  return render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>
          <Explorer />
        </MemoryRouter>
      </QueryClientProvider>
    </I18nextProvider>,
  );
}

const estimate = {
  lat: 28.6139,
  lon: 77.209,
  ts_utc: "2026-10-10T12:00:00Z",
  pm25_low: 120,
  pm25_mid: 160,
  pm25_high: 200,
  category: "Very Poor",
  nearest_station_pm25: 168,
  nearest_station_name: "New Delhi",
  data_age_seconds: 600,
  stale: false,
  model_version: "pkl:abc",
  served_by: "nearest-station",
  cpcb_table_version: "2014-11",
  honesty: "Estimate, not a measurement.",
  demo_mode: true,
};

beforeEach(() => vi.restoreAllMocks());

describe("Explorer", () => {
  it("shows the estimate with the honesty note in demo mode", async () => {
    vi.spyOn(apiLib.api, "estimate").mockResolvedValue(estimate);
    vi.spyOn(apiLib.api, "stations").mockResolvedValue([]);
    vi.spyOn(apiLib.api, "sources").mockResolvedValue({
      query: {},
      wind_from_deg: 292,
      count: 0,
      sources: [],
      openness_note: "heuristic",
    });
    wrap();
    await waitFor(() =>
      expect(screen.getAllByTestId("estimate-value").length).toBeGreaterThan(0),
    );
    expect(screen.getAllByTestId("honesty").length).toBeGreaterThan(0);
    const served = screen.getAllByTestId("served-by");
    expect(served[0]?.textContent ?? "").toContain("nearest-station");
  });

  it("renders the map application region", async () => {
    vi.spyOn(apiLib.api, "estimate").mockResolvedValue(estimate);
    vi.spyOn(apiLib.api, "stations").mockResolvedValue([]);
    vi.spyOn(apiLib.api, "sources").mockResolvedValue({
      query: {},
      wind_from_deg: null,
      count: 0,
      sources: [],
      openness_note: "",
    });
    wrap();
    await waitFor(() => expect(screen.getAllByTestId("map").length).toBeGreaterThan(0));
  });
});

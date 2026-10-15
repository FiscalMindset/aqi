import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import i18n from "../../src/i18n";
import { EstimatePanel } from "../../src/features/explorer/EstimatePanel";
import type { Estimate } from "../../src/lib/api";

function withI18n(ui: React.ReactNode) {
  return render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>);
}

const estimate: Estimate = {
  lat: 28.6139,
  lon: 77.209,
  ts_utc: "2026-10-10T12:00:00Z",
  pm25_low: 120,
  pm25_mid: 160,
  pm25_high: 200,
  category: "Very Poor",
  nearest_station_pm25: 168,
  nearest_station_name: "New Delhi",
  data_age_seconds: 900,
  stale: false,
  model_version: "pkl:abc",
  served_by: "model",
  cpcb_table_version: "2014-11",
  honesty: "Estimate, not a measurement.",
  persistence_anchor_ugm3: 226,
  model_adjustment_ugm3: -2.6,
  method: "gradient-boosted-trees on persistence-anchored residual",
  weather: {
    wind_speed_ms: 2.5,
    wind_gust_ms: 4.0,
    wind_from_deg: 292,
    wind_from_label: "west-northwest",
    temperature_c: 18,
    relative_humidity_pct: 62,
    precipitation_mm: 0,
    age_seconds: 1800,
    stale: false,
    ventilation: "moderate",
    ventilation_reason: "there is light wind, so pollution disperses only slowly",
  },
  cross_check: null,
  features_used: [
    {
      name: "station_lag24",
      value: 226,
      unit: "dimensionless",
      reference: 0,
      contribution_ugm3: -10.3,
      absolute_effect_ugm3: 10.3,
    },
    {
      name: "wind_dir_cos",
      value: 0.74,
      unit: "dimensionless",
      reference: 1,
      contribution_ugm3: 5.5,
      absolute_effect_ugm3: 5.5,
    },
  ],
};

describe("EstimatePanel", () => {
  it("shows the estimate, interval and category", () => {
    withI18n(<EstimatePanel estimate={estimate} loading={false} />);
    expect(screen.getByTestId("estimate-value").textContent).toContain("160");
    expect(screen.getByTestId("estimate-panel").textContent).toContain("120");
    expect(screen.getByTestId("estimate-panel").textContent).toContain("200");
    expect(screen.getByText("Very Poor")).toBeDefined();
  });

  it("always shows the honesty note and the station reading", () => {
    withI18n(<EstimatePanel estimate={estimate} loading={false} />);
    expect(screen.getByTestId("honesty").textContent).toContain(
      "Estimate, not a measurement",
    );
    expect(screen.getByTestId("station-reading").textContent).toContain("New Delhi");
  });

  it("shows a stale indicator when data is stale", () => {
    withI18n(
      <EstimatePanel estimate={{ ...estimate, stale: true }} loading={false} />,
    );
    expect(screen.getByText(/stale/i)).toBeDefined();
  });

  it("renders a skeleton while loading", () => {
    withI18n(<EstimatePanel loading={true} />);
    expect(document.querySelector('[aria-busy="true"]')).toBeTruthy();
  });

  it("renders an error state with a retry affordance", () => {
    withI18n(<EstimatePanel loading={false} error={new Error("boom")} />);
    expect(screen.getByRole("alert")).toBeDefined();
  });
});

describe("EstimatePanel loading state", () => {
  // The loading state used to be one empty block, which reads as "nothing here"
  // rather than "working". It must mirror the real card so the panel does not
  // jump when the number arrives, and it must say what it is doing.
  it("renders a structured placeholder, not an empty box", () => {
    render(<EstimatePanel loading />);
    const box = screen.getByTestId("estimate-loading");
    expect(box).toBeTruthy();
    expect(box.getAttribute("aria-busy")).toBe("true");
    // disc + two text bars + chip
    expect(box.querySelectorAll(".skeleton").length).toBeGreaterThanOrEqual(4);
  });

  it("tells assistive tech it is estimating", () => {
    render(<EstimatePanel loading />);
    expect(screen.getByTestId("estimate-loading").textContent).toMatch(/estimating/i);
  });

  it("shows no value while loading, so a stale number is never implied", () => {
    render(<EstimatePanel loading />);
    expect(screen.queryByTestId("estimate-value")).toBeNull();
  });

  it("shows the value once loaded", () => {
    render(<EstimatePanel estimate={estimate} loading={false} />);
    expect(screen.queryByTestId("estimate-loading")).toBeNull();
    expect(screen.getByTestId("estimate-value")).toBeTruthy();
  });
});

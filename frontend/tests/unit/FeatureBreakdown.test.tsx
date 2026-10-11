import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FeatureBreakdown } from "../../src/features/explorer/FeatureBreakdown";
import { ModelCardPanel } from "../../src/features/explorer/ModelCardPanel";
import type { FeatureContribution, ModelCard } from "../../src/lib/api";

const features: FeatureContribution[] = [
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
  {
    name: "wind_gust",
    value: 6.1,
    unit: "m/s",
    reference: 4,
    contribution_ugm3: 3.1,
    absolute_effect_ugm3: 3.1,
  },
  {
    name: "rh",
    value: 86,
    unit: "%",
    reference: 50,
    contribution_ugm3: -2,
    absolute_effect_ugm3: 2,
  },
  {
    name: "temp_c",
    value: 31,
    unit: "degC",
    reference: 25,
    contribution_ugm3: -0.8,
    absolute_effect_ugm3: 0.8,
  },
  {
    name: "precip",
    value: 0,
    unit: "mm",
    reference: 0,
    contribution_ugm3: 0.1,
    absolute_effect_ugm3: 0.1,
  },
  {
    name: "landfill_count_5km",
    value: 3,
    unit: "count within 5 km",
    reference: 0,
    contribution_ugm3: -0.05,
    absolute_effect_ugm3: 0.05,
  },
];

describe("FeatureBreakdown", () => {
  it("shows the persistence baseline and the model adjustment separately", () => {
    render(
      <FeatureBreakdown
        features={features}
        anchor={226}
        adjustment={-2.6}
        finalValue={223.4}
      />,
    );
    expect(screen.getByTestId("feature-breakdown")).toBeDefined();
    expect(screen.getByText(/Nearest station, 1 h ago/i)).toBeDefined();
    // the arithmetic the user is actually asking about
    expect(screen.getByText("226")).toBeDefined();
    expect(screen.getByText(/-2\.6 model/)).toBeDefined();
    expect(screen.getByText("223 µg/m³")).toBeDefined();
  });

  it("names parameters in plain language and shows their values", () => {
    render(
      <FeatureBreakdown features={features} anchor={226} adjustment={-2.6} finalValue={223.4} />,
    );
    expect(screen.getAllByText("Nearest station, 24 h ago").length).toBeGreaterThan(0);
    expect(screen.getByText("Wind gusts")).toBeDefined();
    expect(screen.getByText("6.1 m/s")).toBeDefined();
  });

  it("renders nothing when the server reported no model attribution", () => {
    const { container } = render(
      <FeatureBreakdown features={[]} anchor={null} adjustment={null} finalValue={100} />,
    );
    expect(container.innerHTML).toBe("");
  });
});

const card: ModelCard = {
  algorithm: "HistGradientBoostingRegressor (scikit-learn), quantile loss",
  trained_at_utc: "2026-10-11T21:28:42+00:00",
  snapshot_sha256: "abc123def456",
  n_rows: 22106,
  stations: [
    { location_id: 8039, rows: 7352 },
    { location_id: 8118, rows: 7481 },
  ],
  temporal_holdout: {
    n_train: 17830,
    n_test: 4276,
    mae: 18.06,
    rmse: 49.79,
    r2: 0.742,
    bias: -4.32,
    coverage80: 0.8,
    mean_width: 41.8,
  },
  leave_one_station_out: {
    n_train: 14833,
    n_test: 22106,
    mae: 129.93,
    rmse: 331.47,
    r2: -0.017,
    bias: 121.46,
    coverage80: 0.38,
    mean_width: 16.5,
  },
  baselines: {
    "persistence-lag1h": {
      n_train: 17830,
      n_test: 4276,
      mae: 24.89,
      rmse: 72.98,
      r2: 0.445,
      bias: -12.12,
      coverage80: null,
      mean_width: null,
    },
  },
  winner: "quantile-model",
  features: ["hour", "wind_speed"],
  n_features: 27,
  conformal_radius_ugm3: 20.89,
  notes: ["conformal radius (80% target): 20.89 ug/m3"],
};

describe("ModelCardPanel", () => {
  it("reports real held-out numbers rather than a marketing claim", () => {
    render(<ModelCardPanel card={card} />);
    expect(screen.getByTestId("model-card")).toBeDefined();
    expect(screen.getAllByText("18.1").length).toBeGreaterThan(0); // MAE
    expect(screen.getAllByText("0.742").length).toBeGreaterThan(0); // R2
    expect(screen.getByTestId("model-vs-baseline")).toBeDefined();
  });

  it("states the weak case plainly: an unseen station is much worse", () => {
    render(<ModelCardPanel card={card} />);
    expect(screen.getByText("129.9")).toBeDefined();
    expect(screen.getByText(/never seen/i)).toBeDefined();
  });

  it("renders nothing without a card", () => {
    const { container } = render(<ModelCardPanel card={null} />);
    expect(container.innerHTML).toBe("");
  });
});
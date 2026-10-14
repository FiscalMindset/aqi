import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModelCardPanel } from "../../src/features/explorer/ModelCardPanel";
import type { ModelCard, ModelMetrics } from "../../src/lib/api";

const base = {
  mae: 11.116,
  rmse: 26.29,
  r2: 0.535,
  bias: 0.2,
  coverage80: 0.377,
  n_train: 473041,
  n_test: 118331,
  mean_width: 30,
} satisfies ModelMetrics;

const card: ModelCard = {
  algorithm: "HistGradientBoostingRegressor (scikit-learn), quantile loss at p10/p50/p90",
  trained_at_utc: "2026-10-12T00:00:00+00:00",
  snapshot_sha256: "c7836258415ae075b78a42495f23025871f36047348589588e039da60152ab7a",
  n_rows: 591372,
  stations: [
    { location_id: 8239, rows: 9651 },
    { location_id: 5586, rows: 9584 },
    { location_id: 8118, rows: 2365 },
  ],
  temporal_holdout: base,
  leave_one_station_out: {
    ...base,
    mae: 10.58,
    rmse: 21.65,
    r2: 0.566,
    coverage80: 0.43,
    n_test: 591372,
  },
  baselines: {
    "persistence-lag1h": { ...base, mae: 11.64 },
    "global-mean": { ...base, mae: 27.15 },
    "per-station-climatology": { ...base, mae: 27.28 },
  },
  winner: "quantile-model",
  features: ["station_lag1", "wind_dir_sin", "hour_sin"],
  n_features: 27,
  conformal_radius_ugm3: 15.0,
  notes: ["conformal radius 15.00 ug/m3"],
};

describe("ModelCardPanel", () => {
  it("renders nothing until the card has loaded", () => {
    const { container } = render(<ModelCardPanel card={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("switches the headline metrics between the two validation protocols", async () => {
    const user = userEvent.setup();
    render(<ModelCardPanel card={card} />);

    // default is the temporal holdout
    expect(screen.getByTestId("protocol-note").textContent).toMatch(/future hours/i);

    await user.click(screen.getByRole("tab", { name: /Unseen station/i }));

    const note = screen.getByTestId("protocol-note");
    expect(note.textContent).toMatch(/never seen/i);
    // the harder protocol's own numbers, not the temporal ones
    expect(note.textContent).toMatch(/never seen using only its neighbours/i);
  });

  it("exposes every pipeline stage as a button that reveals its formula", async () => {
    const user = userEvent.setup();
    render(<ModelCardPanel card={card} />);

    expect(screen.getAllByRole("listitem").length).toBeGreaterThan(0);
    const steps = screen.getByTestId("pipeline-steps").querySelectorAll("button");
    expect(steps.length).toBe(5);

    // first stage starts on the anchor
    expect(screen.getByTestId("pipeline-step").textContent).toMatch(/anchor/i);

    await user.click(steps[2]!);
    const step = screen.getByTestId("pipeline-step");
    expect(step.textContent).toMatch(/residual/i);
    expect(step.textContent).toMatch(/pm25 − station_lag1/);
  });

  it("marks every step it visits as current for assistive tech", async () => {
    const user = userEvent.setup();
    render(<ModelCardPanel card={card} />);
    const steps = screen.getByTestId("pipeline-steps").querySelectorAll("button");
    await user.click(steps[3]!);
    expect(steps[3]!.getAttribute("aria-current")).toBe("true");
    expect(steps[0]!.getAttribute("aria-current")).toBe("false");
  });

  it("compares the model against every measured baseline", () => {
    render(<ModelCardPanel card={card} />);
    const bars = screen.getByTestId("baseline-bars").textContent ?? "";
    expect(bars).toMatch(/quantile-model \(this model\)/);
    expect(bars).toMatch(/persistence-lag1h/);
    expect(bars).toMatch(/global-mean/);
    expect(bars).toMatch(/per-station-climatology/);
  });

  it("filters the station list instead of printing an unreadable comma blob", async () => {
    const user = userEvent.setup();
    render(<ModelCardPanel card={card} />);

    expect(screen.getByTestId("station-list").textContent).toMatch(/8239/);

    await user.type(screen.getByTestId("station-filter"), "8118");
    const list = screen.getByTestId("station-list").textContent ?? "";
    expect(list).toMatch(/8118/);
    expect(list).not.toMatch(/8239/);
  });

  it("reports no match rather than showing a stale list", async () => {
    const user = userEvent.setup();
    render(<ModelCardPanel card={card} />);
    await user.type(screen.getByTestId("station-filter"), "999999");
    expect(screen.getByTestId("station-list").textContent).toMatch(/no station matches/i);
  });

  it("does not claim the interval is wider than it is", () => {
    render(<ModelCardPanel card={card} />);
    // coverage is 37.7%, well under the 80% target, and the card must say so
    expect(document.body.textContent).toMatch(/narrower than claimed/i);
  });

  it("keeps the honest limit visible", () => {
    render(<ModelCardPanel card={card} />);
    expect(document.body.textContent).toMatch(/much weaker at/i);
  });
});
describe("ModelCardPanel rendering paths", () => {

  it("says so when a protocol has no coverage figure", () => {
    const withNull: ModelCard = {
      ...card,
      temporal_holdout: { ...card.temporal_holdout, coverage80: null },
    };
    render(<ModelCardPanel card={withNull} />);
    const table = document.body.textContent ?? "";
    // an em dash, not "NaN%" or a silently invented 80%
    expect(table).toMatch(/—/);
    expect(table).not.toMatch(/NaN/);
  });

  it("does not claim the interval is narrow when coverage is at or above target", () => {
    const good: ModelCard = {
      ...card,
      temporal_holdout: { ...card.temporal_holdout, coverage80: 0.82 },
    };
    render(<ModelCardPanel card={good} />);
    expect(document.body.textContent).not.toMatch(/narrower than claimed/i);
  });

  it("says plainly when the model does not beat the baseline", () => {
    const worse: ModelCard = {
      ...card,
      temporal_holdout: { ...card.temporal_holdout, mae: 30.0 },
    };
    render(<ModelCardPanel card={worse} />);
    expect(document.body.textContent).toMatch(/does not yet beat/i);
  });

  it("still renders with no baselines recorded at all", () => {
    render(<ModelCardPanel card={{ ...card, baselines: {} }} />);
    expect(screen.getByTestId("model-card")).toBeTruthy();
    expect(screen.queryByTestId("model-vs-baseline")).toBeNull();
  });

  it("tolerates a card with no feature list", () => {
    render(<ModelCardPanel card={{ ...card, features: [] }} />);
    expect(screen.getByTestId("model-card")).toBeTruthy();
  });

  it("shows the snapshot digest so the number can be traced to its data", () => {
    render(<ModelCardPanel card={card} />);
    expect(document.body.textContent).toMatch(/c7836258415ae075/);
  });

  it("reports zero stations honestly rather than hiding the limit", () => {
    render(<ModelCardPanel card={{ ...card, stations: [] }} />);
    expect(document.body.textContent).toMatch(/0 stations in training/);
  });

  it("renders the winner name and the conformal radius", () => {
    render(<ModelCardPanel card={card} />);
    const text = document.body.textContent ?? "";
    expect(text).toMatch(/quantile-model/);
    expect(text).toMatch(/15\.0/);
  });
});

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import i18n from "../../src/i18n";
import { Subscribe } from "../../src/features/subscribe/Subscribe";
import { RoutesCompare } from "../../src/features/routes/RoutesCompare";
import * as apiLib from "../../src/lib/api";

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </I18nextProvider>,
  );
}

beforeEach(() => vi.restoreAllMocks());

const estimate = {
  lat: 28.65,
  lon: 77.2,
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
  served_by: "model",
  cpcb_table_version: "2014-11",
  honesty: "Estimate, not a measurement.",
  demo_mode: false,
};

describe("Subscribe", () => {
  it("submits and reports the confirmation flow", async () => {
    vi.spyOn(apiLib.api, "subscribe").mockResolvedValue({
      id: "abc123",
      status: "pending_confirmation",
      locality: "Rohini",
    });
    wrap(<Subscribe />);
    const user = userEvent.setup();
    await user.type(screen.getByTestId("sub-email"), "parent@example.com");
    await user.click(screen.getByTestId("sub-submit"));
    await waitFor(() => expect(screen.getByTestId("sub-message")).toBeDefined());
    expect(screen.getByTestId("sub-message").textContent).toContain("confirmation");
  });

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
    const user = userEvent.setup();
    await user.type(screen.getByTestId("sub-email"), "x@example.com");
    await user.click(screen.getByTestId("sub-submit"));
    await waitFor(() => expect(screen.getByRole("alert")).toBeDefined());
  });
});

describe("RoutesCompare", () => {
  it("renders both route cards with the midpoint estimate", async () => {
    vi.spyOn(apiLib.api, "estimate").mockResolvedValue(estimate);
    wrap(<RoutesCompare />);
    await waitFor(() => expect(screen.getByTestId("route-direct")).toBeDefined());
    expect(screen.getByTestId("route-alt")).toBeDefined();
  });
});

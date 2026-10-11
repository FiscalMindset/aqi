import { test, expect } from "@playwright/test";

/** The demo-mode mock: /v1/* return the recorded snapshot from fixtures. */

const DEMO_HEADER = { "x-dhuan-demo": "1" };

async function mockApi(page: import("@playwright/test").Page) {
  await page.route("**/v1/estimate*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { ...DEMO_HEADER },
      body: JSON.stringify({
        lat: 28.6139,
        lon: 77.209,
        ts_utc: new Date().toISOString(),
        pm25_low: 120,
        pm25_mid: 160,
        pm25_high: 200,
        category: "Very Poor",
        nearest_station_pm25: 168,
        nearest_station_name: "New Delhi",
        data_age_seconds: 600,
        stale: false,
        model_version: "pkl:demo",
        served_by: "nearest-station",
        cpcb_table_version: "2014-11",
        honesty: "Estimate, not a measurement.",
        demo_mode: true,
      }),
    }),
  );
  await page.route("**/v1/stations*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    }),
  );
  await page.route("**/v1/sources*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        query: {},
        wind_from_deg: 292,
        count: 1,
        sources: [
          {
            osm_id: "way/1",
            type: "landfill",
            name: "Bhalswa Landfill Area",
            latitude: 28.72,
            longitude: 77.16,
            distance_km: 12.0,
            bearing_deg: 292,
            in_upwind_cone: true,
            influence_score: 0.6,
            area_m2: 120000,
            attribution: "© OpenStreetMap contributors (ODbL)",
          },
        ],
        openness_note: "heuristic",
      }),
    }),
  );
  await page.route("**/v1/explain", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        lat: 28.6139,
        lon: 77.209,
        served_by: "scripted-deterministic",
        attribution: {
          summary: "Likely contributors: landfill upwind.",
          likely_causes: [
            {
              rank: 1,
              category: "landfill",
              label: "Landfill (Bhalswa Landfill Area)",
              band: "High",
              evidence_ids: ["ev_1"],
              reasoning: "12 km upwind; influence 0.60",
              distance_km: 12,
              bearing_deg: 292,
            },
          ],
          confidence: "medium",
          confidence_reason: "partial evidence",
          evidence: [
            {
              evidence_id: "ev_1",
              tool: "find_upwind_sources",
              args: { lat: 28.6139, lon: 77.209 },
              summary: "1 candidate source within 15 km upwind",
              fetched_at: new Date().toISOString(),
              ok: true,
            },
          ],
          tool_calls: ["find_upwind_sources(...)"],
          demo_mode: true,
        },
        advice: [
          {
            persona: "parent",
            headline: "children should limit outdoor time",
            actions: ["keep play short"],
            evidence_ids: ["ev_1"],
            disclaimer: "General guidance.",
          },
        ],
        demo_mode: true,
        note: "",
      }),
    }),
  );
  await page.route("**/v1/validation", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        version: "eval-1",
        created_utc: "2026-10-10T00:00:00Z",
        n_rows: 22106,
        temporal_holdout: { mae: 26.1, rmse: 59.8, r2: 0.63, bias: -18.3 },
        loso_mean: { mae: 131.6 },
        baselines: { "persistence-lag1h": { mae: 24.9 } },
        winner: "nearest-station-baseline (persistence-lag1h)",
        interval_coverage_note: "conformal 0.800",
      }),
    }),
  );
  await page.route("**/v1/status", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        api_version: "0.1.0",
        model_version: "baseline-v1",
        feeds: [],
        coverage: {},
        demo_mode: true,
      }),
    }),
  );
}

test.describe("core journeys", () => {
  test("explorer shows the estimate with honesty and demo banner", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await expect(page.getByTestId("estimate-panel").first()).toBeVisible();
    await expect(page.getByTestId("estimate-value").first()).toContainText("160");
    // rule 1: demo banner is permanent and visible
    await expect(page.getByTestId("demo-banner")).toBeVisible();
    await expect(page.getByTestId("honesty").first()).toContainText(
      "Estimate, not a measurement",
    );
  });

  test("explanation reveals the agent trace with evidence", async ({ page }, testInfo) => {
    await mockApi(page);
    await page.goto("/");
    // mobile: expand the bottom sheet first (peek only shows the estimate)
    if (testInfo.project.name === "mobile-chrome") {
      await page.getByTestId("bottom-sheet").locator("button").first().click();
    }
    await page.getByTestId("explain-toggle").first().click();
    await expect(page.getByTestId("agent-trace").first()).toBeVisible();
    await expect(page.getByTestId("tool-calls").first()).toContainText(
      "find_upwind_sources",
    );
    await expect(page.getByTestId("causes-panel").first()).toContainText("Bhalswa");
    await expect(page.getByTestId("persona-cards").first()).toContainText("parent");
  });

  test("deep link renders a location result", async ({ page }) => {
    await mockApi(page);
    await page.goto("/place/28.6139/77.209");
    await expect(page.getByTestId("estimate-panel").first()).toBeVisible();
  });

  test("language switch persists across reloads", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await page.getByTestId("lang-hi").first().click();
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "hi");
    await expect(page.getByTestId("lang-hi").first()).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  test("status page lists feeds", async ({ page }) => {
    await mockApi(page);
    await page.goto("/status");
    await expect(page.getByTestId("status-page")).toBeVisible();
  });

  test("methodology shows the real winner", async ({ page }) => {
    await mockApi(page);
    await page.goto("/methodology");
    await expect(page.getByTestId("winner")).toContainText("nearest-station-baseline");
    await expect(page.getByTestId("val-mae")).toContainText("26.1");
  });
});

test.describe("problem handling", () => {
  test("outside coverage shows the honest problem message", async ({ page }) => {
    await page.route("**/v1/estimate*", (route) =>
      route.fulfill({
        status: 422,
        contentType: "application/problem+json",
        body: JSON.stringify({
          type: "https://x/problems/outside-coverage",
          title: "Point outside coverage",
          status: 422,
          detail: "The point is not inside the Delhi-NCR coverage polygon.",
        }),
      }),
    );
    await page.route("**/v1/stations*", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
    );
    await page.route("**/v1/sources*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ query: {}, wind_from_deg: null, count: 0, sources: [], openness_note: "" }),
      }),
    );
    await page.goto("/place/19.076/72.877");
    await expect(page.getByRole("alert").first()).toBeVisible();
  });
});

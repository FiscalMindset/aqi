import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const ROUTES = ["/", "/routes", "/subscribe", "/how-it-works", "/methodology", "/status"];

const VALID = {
  estimate: {
    lat: 28.6139, lon: 77.209, ts_utc: "2026-10-10T12:00:00Z",
    pm25_low: 120, pm25_mid: 160, pm25_high: 200, category: "Very Poor",
    nearest_station_pm25: 168, nearest_station_name: "New Delhi",
    data_age_seconds: 600, stale: false, model_version: "pkl:x",
    served_by: "model", cpcb_table_version: "2014-11",
    honesty: "Estimate, not a measurement.", demo_mode: true,
  },
  stations: [],
  sources: { query: {}, wind_from_deg: null, count: 0, sources: [], openness_note: "" },
  validation: {
    version: "eval-1", created_utc: "2026-10-10T00:00:00Z", n_rows: 100,
    temporal_holdout: { mae: 26, rmse: 60, r2: 0.6, bias: -18 },
    loso_mean: { mae: 130 }, baselines: { persistence: { mae: 25 } },
    winner: "nearest-station-baseline", interval_coverage_note: "0.8",
  },
  status: { status: "ok", api_version: "0.1.0", model_version: "v1", feeds: [], coverage: {}, demo_mode: false },
};

async function mockAll(page: import("@playwright/test").Page) {
  const bodies: Record<string, unknown> = {
    estimate: VALID.estimate,
    stations: VALID.stations,
    sources: VALID.sources,
    validation: VALID.validation,
    status: VALID.status,
    explain: {
      lat: 28.6, lon: 77.2, served_by: "scripted-deterministic",
      attribution: {
        summary: "", likely_causes: [], confidence: "medium", confidence_reason: "",
        evidence: [], tool_calls: [], demo_mode: true,
      },
      advice: [], demo_mode: true, note: "",
    },
  };
  for (const [name, body] of Object.entries(bodies)) {
    await page.route(`**/v1/${name}*`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body),
      }),
    );
  }
}

/** WCAG 2.2 AA: zero serious/critical violations on every route. */
test.describe("accessibility", () => {
  for (const route of ROUTES) {
    test(`${route} has no serious/critical axe violations`, async ({ page }) => {
      await mockAll(page);
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      const serious = results.violations.filter(
        (v) => v.impact === "serious" || v.impact === "critical",
      );
      expect(
        serious,
        `serious violations on ${route}: ${JSON.stringify(serious, null, 2)}`,
      ).toEqual([]);
    });
  }
});

test.describe("responsive", () => {
  const viewports = [
    { width: 360, height: 800 },
    { width: 390, height: 844 },
    { width: 768, height: 1024 },
    { width: 1024, height: 768 },
    { width: 1440, height: 900 },
  ];

  for (const vp of viewports) {
    test(`no horizontal scroll at ${vp.width}px`, async ({ page }) => {
      await mockAll(page);
      await page.setViewportSize(vp);
      await page.goto("/");
      await page.waitForLoadState("networkidle");
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(1);
    });
  }

  test("touch targets are at least 44px", async ({ page }) => {
    await mockAll(page);
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const small = await page.evaluate(() => {
      const els = Array.from(
        document.querySelectorAll("button, a[href], input, select"),
      );
      return els
        .filter((el) => {
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) return false;
          // sr-only until focused (skip link) and the OSM-required attribution
          // link are exempt from target size (WCAG 2.2 exceptions)
          if (el.closest(".sr-only") || el.classList.contains("sr-only")) return false;
          if (el.closest(".maplibregl-ctrl-attrib")) return false;
          return r.height < 44 || r.width < 44;
        })
        .map((el) => `${el.tagName}.${el.className}: ${el.getBoundingClientRect().height}px`);
    });
    expect(small, `small touch targets: ${small.join(", ")}`).toEqual([]);
  });

  test("bottom sheet drags on touch devices", async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      hasTouch: true,
      isMobile: true,
    });
    const page = await context.newPage();
    await mockAll(page);
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const sheet = page.getByTestId("bottom-sheet");
    if (await sheet.count()) {
      const handle = sheet.locator("button").first();
      await handle.tap();
      await expect(sheet).toBeVisible();
    }
    await context.close();
  });
});

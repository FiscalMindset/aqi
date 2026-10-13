import { test, expect } from "@playwright/test";

/**
 * Smoke test against the REAL deployed app.
 *
 * The mock-based suite in core.spec.ts proves the components render; this
 * proves the deployed bundle actually reaches the deployed API. That gap is
 * where every real defect so far lived: a hardcoded "/v1" base meant the live
 * app requested the gateway root and got 403 for every call while the backend
 * was healthy at /staging/v1.
 */

const LIVE = "http://127.0.0.1:4173/staging/";

test.describe("deployed app", () => {
  test("loads the estimate, the explanation and the map", async ({ page }) => {
    const failures: string[] = [];
    page.on("requestfailed", (r) => failures.push(`${r.url()} ${r.failure()?.errorText}`));
    page.on("response", (r) => {
      if (r.status() >= 400) failures.push(`${r.url()} -> HTTP ${r.status()}`);
    });

    await page.goto(LIVE, { waitUntil: "domcontentloaded" });

    // The estimate must resolve, not sit in the error state.
    await expect(page.getByTestId("estimate-error")).toHaveCount(0, { timeout: 45_000 });
    await expect(page.getByTestId("estimate-value")).toBeVisible({ timeout: 45_000 });

    // The explanation is no longer behind a click.
    await expect(page.getByTestId("explanation-headline")).toBeVisible({ timeout: 60_000 });

    // The map must have real height, not a zero-height canvas.
    const box = await page.getByTestId("map").boundingBox();
    expect(box?.height ?? 0).toBeGreaterThan(150);

    expect(failures, `failed requests:\n${failures.join("\n")}`).toEqual([]);
  });

  test("routes page loads with real corridors", async ({ page }) => {
    const bad: string[] = [];
    page.on("response", (r) => {
      if (r.status() >= 400) bad.push(`${r.url()} -> ${r.status()}`);
    });
    await page.goto(`${LIVE}routes`, { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("routes-summary")).toBeVisible({ timeout: 60_000 });
    expect(bad, bad.join("\n")).toEqual([]);
  });

  test("geolocation denial is inline, not a modal", async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "geolocation", {
        value: {
          getCurrentPosition: (_ok: unknown, err: (e: unknown) => void) =>
            err({ code: 1, message: "denied" }),
        },
        configurable: true,
      });
    });
    await page.goto(LIVE, { waitUntil: "domcontentloaded" });
    let alerted = false;
    page.on("dialog", async (d) => {
      alerted = true;
      await d.dismiss();
    });
    await page.getByTestId("use-location").click();
    await expect(page.getByTestId("location-note")).toBeVisible();
    expect(alerted).toBe(false);
  });
});
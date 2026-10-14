import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import i18n from "../../src/i18n";
import { CrossCheck } from "../../src/features/explorer/CrossCheck";
import type { CrossCheck as CC } from "../../src/lib/api";

const base: CC = {
  pm25_ugm3: 68.7,
  us_aqi: 165,
  european_aqi: 69,
  dust_ugm3: 83,
  delta_ugm3: -43.3,
  age_seconds: 170,
  provider: "Open-Meteo Air Quality (CAMS)",
  is_ground_reading: false,
};

function renderIt(data: CC | null, ours: number | null = 25.4) {
  return render(
    <I18nextProvider i18n={i18n}>
      <CrossCheck data={data} ourPm25={ours} />
    </I18nextProvider>,
  );
}

describe("CrossCheck", () => {
  it("shows both numbers side by side rather than only the flattering one", () => {
    renderIt(base);
    expect(screen.getByTestId("cross-check")).toBeTruthy();
    expect(screen.getByTestId("cross-check").textContent).toMatch(/69/);
    expect(screen.getByTestId("cross-check").textContent).toMatch(/25/);
  });

  it("states the gap with a sign so the direction is unambiguous", () => {
    renderIt(base);
    expect(screen.getByTestId("cross-check").textContent).toMatch(/-43\.3/);
  });

  it("says so plainly when there is no independent reading", () => {
    renderIt(null);
    expect(screen.getByTestId("cross-check-unavailable")).toBeTruthy();
    expect(screen.queryByTestId("cross-check")).toBeNull();
  });

  it("treats a missing pm25 as unavailable rather than as zero", () => {
    renderIt({ ...base, pm25_ugm3: null });
    expect(screen.getByTestId("cross-check-unavailable")).toBeTruthy();
  });

  // Delhi's post-monsoon dust season drives the dust column far above any
  // plausible smoke contribution. Rendering it without saying so would let a
  // reader read dust as fire smoke.
  it("flags heavy dust and says it is dust, not smoke", () => {
    renderIt(base);
    const dust = screen.getByTestId("cross-check-dust");
    expect(dust.textContent).toMatch(/83/);
    expect(dust.textContent.toLowerCase()).toContain("not fire smoke");
  });

  it("does not raise a dust note when dust is low", () => {
    renderIt({ ...base, dust_ugm3: 12 });
    expect(screen.queryByTestId("cross-check-dust")).toBeNull();
  });

  it("explains why two different numbers can both be right", () => {
    renderIt(base);
    expect(screen.getByTestId("cross-check").textContent).toMatch(/regional/i);
  });

  it("handles a missing local value without printing NaN", () => {
    renderIt(base, null);
    const text = screen.getByTestId("cross-check").textContent ?? "";
    expect(text).not.toMatch(/NaN|undefined/);
  });
});

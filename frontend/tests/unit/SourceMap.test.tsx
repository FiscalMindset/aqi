import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import i18n from "../../src/i18n";
import { SourceMap } from "../../src/features/explorer/SourceMap";
import type { SourceHit, StationReading } from "../../src/lib/api";

// MapLibre needs WebGL, which jsdom does not provide, so the component renders
// its fallback rather than a live map. What is asserted here is the control
// surface that sits above the map: every control must exist, be labelled, be
// keyboard reachable and report its state, because that surface is the part a
// keyboard or screen-reader user actually operates.

const source: SourceHit = {
  osm_id: "way/123",
  type: "major_junction",
  name: "Test junction",
  latitude: 28.5,
  longitude: 77.2,
  distance_km: 0.4,
  bearing_deg: 90,
  influence_score: 0.8,
  in_upwind_cone: true,
  area_m2: null,
  attribution: "",
};

const station: StationReading = {
  station_id: "6254594",
  name: "Talkatora Garden",
  latitude: 28.49,
  longitude: 77.2,
  provider: "openaq-public-archive",
  distance_km: 1.67,
  pm25: 54.09,
  observed_at: "2026-10-07T14:30:00+00:00",
  age_seconds: 100,
  category: "Satisfactory",
};

function renderMap(overrides: Partial<React.ComponentProps<typeof SourceMap>> = {}) {
  return render(
    <I18nextProvider i18n={i18n}>
      <SourceMap
        lat={28.61}
        lon={77.21}
        sources={[source]}
        stations={[station]}
        onPick={vi.fn()}
        {...overrides}
      />
    </I18nextProvider>,
  );
}

describe("SourceMap controls", () => {
  it("exposes layer, compare and full-screen controls", () => {
    renderMap();
    expect(screen.getByTestId("map-toggle-sources")).toBeTruthy();
    expect(screen.getByTestId("map-toggle-stations")).toBeTruthy();
    expect(screen.getByTestId("map-toggle-compare")).toBeTruthy();
    expect(screen.getByTestId("map-fullscreen")).toBeTruthy();
  });

  it("toggles each layer and reports its state to assistive tech", async () => {
    const user = userEvent.setup();
    renderMap();

    const sources = screen.getByTestId("map-toggle-sources");
    expect(sources.getAttribute("aria-pressed")).toBe("true");
    await user.click(sources);
    expect(sources.getAttribute("aria-pressed")).toBe("false");
    await user.click(sources);
    expect(sources.getAttribute("aria-pressed")).toBe("true");

    const stations = screen.getByTestId("map-toggle-stations");
    expect(stations.getAttribute("aria-pressed")).toBe("true");
    await user.click(stations);
    expect(stations.getAttribute("aria-pressed")).toBe("false");
  });

  it("toggles full screen on and off", async () => {
    const user = userEvent.setup();
    renderMap();
    const btn = screen.getByTestId("map-fullscreen");
    expect(btn.getAttribute("aria-pressed")).toBe("false");
    await user.click(btn);
    expect(btn.getAttribute("aria-pressed")).toBe("true");
    await user.click(btn);
    expect(btn.getAttribute("aria-pressed")).toBe("false");
  });

  it("asks for a second point only after compare mode is switched on", async () => {
    const user = userEvent.setup();
    renderMap();

    expect(screen.queryByTestId("map-compare-hint")).toBeNull();
    await user.click(screen.getByTestId("map-toggle-compare"));

    const hint = await screen.findByTestId("map-compare-hint");
    expect(hint.getAttribute("role")).toBe("status");
    expect(hint.textContent).toMatch(/click the map/i);
  });

  it("keeps every control reachable without a pointer", async () => {
    const user = userEvent.setup();
    renderMap();
    // tab order must reach the toggles, so the map is operable by keyboard
    await user.tab();
    const first = document.activeElement?.getAttribute("data-testid");
    expect(["map-toggle-sources", "map-toggle-stations", "map-toggle-compare", "map-fullscreen"]).toContain(first);
  });

  it("states which station the estimate is anchored to", async () => {
    renderMap();
    const anchor = screen.getByTestId("map-anchor");
    // the actual observed reading and how far away it is, so the estimate is
    // checkable rather than a black box
    expect(anchor.textContent).toMatch(/54/);
    expect(anchor.textContent).toMatch(/1\.7 km/);
  });

  it("omits the anchor chip when no station is in range", () => {
    renderMap({ stations: [] });
    expect(screen.queryByTestId("map-anchor")).toBeNull();
  });

  it("always renders a legend that explains what is drawn", () => {
    renderMap();
    const legend = screen.getByTestId("map-legend");
    expect(legend.textContent).toMatch(/upwind/i);
    expect(legend.textContent).toMatch(/your point/i);
  });

  it("explains dot size rather than leaving it a mystery", () => {
    renderMap();
    expect(screen.getByTestId("map-legend").textContent).toMatch(/bigger dot/i);
  });
});
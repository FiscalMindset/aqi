import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import i18n from "../../src/i18n";
import { SearchBox } from "../../src/features/explorer/SearchBox";
import { allPlaces, searchPlaces } from "../../src/lib/places";

function wrap(onSelect: (lat: number, lon: number) => void) {
  return render(
    <I18nextProvider i18n={i18n}>
      <SearchBox onSelect={onSelect} />
    </I18nextProvider>,
  );
}

describe("SearchBox", () => {
  it("filters places and emits the selection", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    wrap(onSelect);
    await user.type(screen.getByTestId("search-input"), "roh");
    const option = await screen.findByRole("option", { name: /rohini/i });
    expect(option).toBeDefined();
    await user.click(option);
    expect(onSelect).toHaveBeenCalledWith(28.7146, 77.1025);
  });

  it("has a labelled input and a use-location button", async () => {
    const user = userEvent.setup();
    wrap(vi.fn());
    expect(screen.getByTestId("use-location")).toBeDefined();
    // geolocation is not available in jsdom: clicking must not crash
    await user.click(screen.getByTestId("use-location"));
  });
});

describe("SearchBox geolocation note", () => {
  // Regression: the note used to persist until the button was pressed again, so
  // the panel said "Location permission denied" next to a location that had just
  // been chosen from the search box.
  it("clears a denied-location warning once a place is picked from search", async () => {
    const user = userEvent.setup();
    render(
      <I18nextProvider i18n={i18n}>
        <SearchBox onSelect={vi.fn()} />
      </I18nextProvider>,
    );

    const denied = Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: {
        getCurrentPosition: (_ok: PositionCallback, err?: PositionErrorCallback) =>
          err?.({ code: 1, message: "denied" } as GeolocationPositionError),
      },
    });
    await user.click(screen.getByTestId("use-location"));
    expect(await screen.findByTestId("location-note")).toBeTruthy();
    expect(screen.getByTestId("location-note").textContent).toMatch(/denied/i);

    await user.type(screen.getByTestId("search-input"), "ghevra");
    // exact name: the gazetteer also holds "Ghevra Railway Station" and "Ghevra More"
    await user.click(await screen.findByRole("option", { name: "Ghevra" }));

    expect(screen.queryByTestId("location-note")).toBeNull();
    void denied;
  });
});

describe("places gazetteer coverage", () => {
  it("finds Ghevra, which was reported missing", () => {
    expect(searchPlaces("ghevra").map((p) => p.name)).toContain("Ghevra");
  });

  it("keeps every place inside the advertised service area", () => {
    for (const p of allPlaces()) {
      expect(p.lat).toBeGreaterThanOrEqual(26.707);
      expect(p.lat).toBeLessThanOrEqual(29.714);
      expect(p.lon).toBeGreaterThanOrEqual(76.113);
      expect(p.lon).toBeLessThanOrEqual(78.475);
    }
  });

  it("has no duplicate names", () => {
    const names = allPlaces().map((p) => p.name);
    expect(new Set(names).size).toBe(names.length);
  });
});

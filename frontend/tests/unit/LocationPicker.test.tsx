import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import i18n from "../../src/i18n";
import { LocationPicker } from "../../src/features/subscribe/LocationPicker";
import { allPlaces } from "../../src/lib/places";

function mockGeo(
  impl: (ok: PositionCallback, err?: PositionErrorCallback | null) => void,
): void {
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: { getCurrentPosition: impl },
  });
}

function renderPicker(onChange = vi.fn()) {
  render(
    <I18nextProvider i18n={i18n}>
      <LocationPicker value={allPlaces()[0]!} onChange={onChange} />
    </I18nextProvider>,
  );
  return onChange;
}

afterEach(() => {
  // @ts-expect-error -- restore the jsdom default between tests
  delete navigator.geolocation;
  vi.restoreAllMocks();
});

describe("LocationPicker use-my-location", () => {
  it("offers a use-my-location control", () => {
    renderPicker();
    expect(screen.getByTestId("picker-use-location")).toBeTruthy();
  });

  it("keeps the exact coordinates the browser reports, not a place centroid", async () => {
    const user = userEvent.setup();
    mockGeo((ok) =>
      ok({
        coords: { latitude: 28.4721, longitude: 77.1702 },
      } as GeolocationPosition),
    );
    const onChange = renderPicker();

    await user.click(screen.getByTestId("picker-use-location"));

    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const picked = onChange.mock.calls[0]![0] as {
      name: string;
      lat: number;
      lon: number;
    };
    expect(picked.lat).toBeCloseTo(28.4721, 5);
    expect(picked.lon).toBeCloseTo(77.1702, 5);
    // named for the user, but the point is the real position
    expect(picked.name).toContain("My location");
  });

  it("explains itself when permission is denied and stays usable", async () => {
    const user = userEvent.setup();
    mockGeo((_ok, err) =>
      err?.({ code: 1, message: "User denied Geolocation" } as GeolocationPositionError),
    );
    renderPicker();

    await user.click(screen.getByTestId("picker-use-location"));

    const note = await screen.findByTestId("picker-location-note");
    expect(note.textContent).toMatch(/denied/i);
    // and the search box must still work, since that is the fallback
    expect(screen.getByTestId("picker-search")).toBeTruthy();
  });

  it("says so plainly when the browser has no geolocation at all", async () => {
    const user = userEvent.setup();
    // @ts-expect-error -- simulate a browser without the API
    delete navigator.geolocation;
    renderPicker();

    await user.click(screen.getByTestId("picker-use-location"));

    const note = await screen.findByTestId("picker-location-note");
    expect(note.textContent).toMatch(/cannot share your location/i);
  });
});
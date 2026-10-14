import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import i18n from "../../src/i18n";
import { LocationPicker } from "../../src/features/subscribe/LocationPicker";
import { allPlaces, type Place } from "../../src/lib/places";

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
  // @ts-expect-error -- restore the jsdom defaults between tests
  delete navigator.geolocation;
  // @ts-expect-error -- jsdom does not implement the Permissions API
  delete navigator.permissions;
  vi.restoreAllMocks();
});

function mockPermissions(state: PermissionState): void {
  Object.defineProperty(navigator, "permissions", {
    configurable: true,
    value: { query: () => Promise.resolve({ state }) },
  });
}

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
    expect(note.textContent).toMatch(/declined/i);
    // and the search box must still work, since that is the fallback
    expect(screen.getByTestId("picker-search")).toBeTruthy();
  });

  // Regression: getCurrentPosition is async, so a denied attempt started first
  // could report its error *after* a later attempt had already succeeded, which
  // printed "permission denied" beside a location that had just been found.
  // Regression, and the exact thing reported: a denial message left over from an
  // earlier attempt sat on screen *next to* a location that had since been found
  // successfully, so the panel contradicted itself. The complaint must not
  // survive any change of the chosen point.
  it("clears a stale denial once the point changes to a found location", async () => {
    const user = userEvent.setup();
    mockGeo((_ok, err) =>
      err?.({ code: 1, message: "denied" } as GeolocationPositionError),
    );
    const { rerender } = render(
      <I18nextProvider i18n={i18n}>
        <LocationPicker value={allPlaces()[0]!} onChange={vi.fn()} />
      </I18nextProvider>,
    );

    await user.click(screen.getByTestId("picker-use-location"));
    expect(await screen.findByTestId("picker-location-note")).toBeTruthy();

    // the user then finds their position some other way and the point changes
    const found: Place = { name: "My location near Ghevra", lat: 28.4726, lon: 77.1714 };
    rerender(
      <I18nextProvider i18n={i18n}>
        <LocationPicker value={found} onChange={vi.fn()} />
      </I18nextProvider>,
    );

    await waitFor(() =>
      expect(screen.queryByTestId("picker-location-note")).toBeNull(),
    );
  });

  // A late callback from a superseded attempt must not resurrect the warning
  // either: getCurrentPosition is asynchronous, so its error can land after the
  // component has already moved on.
  it("drops an error callback from a superseded attempt", async () => {
    const user = userEvent.setup();
    const box: { release: ((e: GeolocationPositionError) => void) | null } = {
      release: null,
    };
    mockGeo((_ok, err) => {
      box.release = (e) => err?.(e);
    });
    const { rerender } = render(
      <I18nextProvider i18n={i18n}>
        <LocationPicker value={allPlaces()[0]!} onChange={vi.fn()} />
      </I18nextProvider>,
    );

    await user.click(screen.getByTestId("picker-use-location"));
    rerender(
      <I18nextProvider i18n={i18n}>
        <LocationPicker
          value={{ name: "Ghevra", lat: 28.4726, lon: 77.1714 }}
          onChange={vi.fn()}
        />
      </I18nextProvider>,
    );

    // the superseded attempt now finally reports a denial
    box.release?.({ code: 1, message: "denied" } as GeolocationPositionError);
    await new Promise((r) => setTimeout(r, 10));

    expect(screen.queryByTestId("picker-location-note")).toBeNull();
  });

  it("explains a permission the browser has blocked outright", async () => {
    const user = userEvent.setup();
    mockGeo(() => {
      throw new Error("should not request once the state is known to be denied");
    });
    mockPermissions("denied");
    renderPicker();

    await user.click(screen.getByTestId("picker-use-location"));

    const note = await screen.findByTestId("picker-location-note");
    expect(note.textContent).toMatch(/blocked/i);
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
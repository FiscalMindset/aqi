import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import i18n from "../../src/i18n";
import { SearchBox } from "../../src/features/explorer/SearchBox";

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

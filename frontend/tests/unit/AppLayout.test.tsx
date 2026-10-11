import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import i18n from "../../src/i18n";
import { AppLayout } from "../../src/app/AppLayout";

function renderLayout() {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter>
        <AppLayout />
      </MemoryRouter>
    </I18nextProvider>,
  );
}

describe("AppLayout", () => {
  it("renders header, main region and attribution footer", () => {
    renderLayout();
    expect(screen.getByRole("banner")).toBeDefined();
    expect(screen.getByRole("main")).toBeDefined();
    expect(screen.getByRole("contentinfo").textContent).toContain("OpenAQ");
    expect(screen.getByRole("contentinfo").textContent).toContain("OpenStreetMap contributors");
  });

  it("has a skip link and accessible navigation", () => {
    renderLayout();
    expect(screen.getByRole("link", { name: /skip to content/i })).toBeDefined();
    expect(screen.getAllByRole("navigation").length).toBeGreaterThan(0);
  });

  it("shows the offline banner role slot on route content", () => {
    renderLayout();
    // online in jsdom by default -> no offline banner, and demo off by default
    expect(screen.queryByTestId("offline-banner")).toBeNull();
    expect(screen.queryByTestId("demo-banner")).toBeNull();
  });
});

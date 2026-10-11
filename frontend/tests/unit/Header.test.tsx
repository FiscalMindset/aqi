import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import i18n from "../../src/i18n";
import { Header } from "../../src/components/Header";

function withI18n(ui: React.ReactNode) {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter>{ui}</MemoryRouter>
    </I18nextProvider>,
  );
}

describe("Header", () => {
  it("renders the primary navigation", () => {
    withI18n(<Header />);
    expect(screen.getAllByRole("link", { name: /explorer/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /methodology/i }).length).toBeGreaterThan(0);
  });

  it("switches language and persists it", async () => {
    withI18n(<Header />);
    const hi = screen.getAllByTestId("lang-hi")[0]!;
    hi.click();
    await vi.waitFor(() => expect(i18n.resolvedLanguage).toBe("hi"));
    expect(localStorage.getItem("dhuan.language")).toBe("hi");
    const en = screen.getAllByTestId("lang-en")[0]!;
    en.click();
    await vi.waitFor(() => expect(i18n.resolvedLanguage).toBe("en"));
    expect(localStorage.getItem("dhuan.language")).toBe("en");
  });
});

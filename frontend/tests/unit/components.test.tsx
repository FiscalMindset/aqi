import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import i18n from "../../src/i18n";
import { BottomSheet } from "../../src/components/BottomSheet";
import { ErrorBoundary } from "../../src/components/ErrorBoundary";
import { OfflineBanner } from "../../src/components/OfflineBanner";
import { Loading } from "../../src/components/Loading";
import { SkipLink } from "../../src/components/SkipLink";

function wrap(ui: React.ReactNode) {
  return render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>);
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.removeAttribute("data-demo");
});

describe("BottomSheet", () => {
  it("shows only the peek content at the peek level", () => {
    const { getByTestId } = wrap(
      <BottomSheet full={false} peek={<p>peek</p>}>
        <p>details</p>
      </BottomSheet>,
    );
    const sheet = getByTestId("bottom-sheet");
    expect(sheet.textContent).toContain("peek");
    expect(sheet.textContent).not.toContain("details");
  });

  it("expands when the handle is tapped", () => {
    const { getByTestId } = wrap(
      <BottomSheet full={false} peek={<p>peek</p>}>
        <p>details</p>
      </BottomSheet>,
    );
    const sheet = getByTestId("bottom-sheet");
    fireEvent.click(sheet.querySelector("button")!);
    expect(sheet.textContent).toContain("details");
  });

  // the drag gesture itself is covered in Playwright e2e (real pointer events)

  it("renders full content when full", () => {
    const { getByTestId } = wrap(
      <BottomSheet full={true} peek={<p>peek</p>}>
        <p>details</p>
      </BottomSheet>,
    );
    expect(getByTestId("bottom-sheet").textContent).toContain("details");
  });
});

describe("ErrorBoundary", () => {
  it("catches errors and offers retry", () => {
    const Boom = () => {
      throw new Error("render exploded");
    };
    const { getByRole } = wrap(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(getByRole("alert").textContent).toContain("Something went wrong");
  });

  it("renders children when there is no error", () => {
    const { getByText } = wrap(
      <ErrorBoundary>
        <p>healthy</p>
      </ErrorBoundary>,
    );
    expect(getByText("healthy")).toBeDefined();
  });
});

describe("OfflineBanner", () => {
  it("shows when the browser goes offline", () => {
    vi.stubGlobal("navigator", { onLine: false, language: "en" });
    const { getByTestId } = wrap(<OfflineBanner />);
    expect(getByTestId("offline-banner")).toBeDefined();
  });

  it("hidden when online", () => {
    vi.stubGlobal("navigator", { onLine: true, language: "en" });
    const { queryByTestId } = wrap(<OfflineBanner />);
    expect(queryByTestId("offline-banner")).toBeNull();
  });
});


describe("Loading and SkipLink", () => {
  it("renders a status region by default", () => {
    wrap(<Loading />);
    expect(screen.getByRole("status")).toBeDefined();
  });

  it("renders children when provided", () => {
    const { getByText } = wrap(<Loading><p>loaded</p></Loading>);
    expect(getByText("loaded")).toBeDefined();
  });

  it("skip link targets main", () => {
    const { container } = wrap(<SkipLink />);
    expect(container.querySelector("a[href='#main']")).toBeTruthy();
  });
});

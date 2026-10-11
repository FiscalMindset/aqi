import "@testing-library/jest-dom/vitest";

// jsdom does not implement matchMedia. Explorer uses a reactive media query to
// switch between the desktop split view and the mobile bottom sheet, so any
// test that renders it needs this stub. Matches are mutable so a test can force
// desktop or mobile.
let matches = true;
Object.defineProperty(window, "matchMedia", {
  writable: true,
  configurable: true,
  value: (query: string): MediaQueryList =>
    ({
      matches,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList,
});

export function setMediaMatches(value: boolean): void {
  matches = value;
}
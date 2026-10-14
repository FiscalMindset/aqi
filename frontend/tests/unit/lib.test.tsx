import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { searchPlaces } from "../../src/lib/places";
import { CATEGORY_COLORS, onColor } from "../../src/lib/aqi";
import AqiIcon from "../../src/components/AqiIcon";

describe("places", () => {
  it("finds Delhi-NCR localities case-insensitively", () => {
    expect(searchPlaces("rohini").map((p) => p.name)).toContain("Rohini");
    expect(searchPlaces("dwarka").map((p) => p.name)).toContain("Dwarka");
  });

  it("returns nothing for an empty query", () => {
    expect(searchPlaces("")).toHaveLength(0);
  });

  it("is bounded", () => {
    expect(searchPlaces("a", 3).length).toBeLessThanOrEqual(3);
  });
});

describe("aqi palette", () => {
  it("maps every CPCB category to a color", () => {
    for (const cat of [
      "Good",
      "Satisfactory",
      "Moderately Polluted",
      "Poor",
      "Very Poor",
      "Severe",
    ]) {
      expect(CATEGORY_COLORS[cat]).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });

  it("pairs color with an icon for every category (WCAG)", () => {
    for (const cat of Object.keys(CATEGORY_COLORS)) {
      expect(onColor(cat)).toMatch(/^#/);
    }
  });

  // Regression: the category mark used to be a Unicode geometric glyph. Those
  // characters are missing from most system fonts, so users saw a tofu box beside
  // their value instead of a coloured shape. Assert a drawn SVG mark instead.
  it("draws an SVG mark for every category rather than a font glyph", () => {
    for (const cat of Object.keys(CATEGORY_COLORS)) {
      const { container } = render(<AqiIcon category={cat} />);
      const svg = container.querySelector("svg");
      expect(svg, `no svg for ${cat}`).not.toBeNull();
      expect(svg?.childNodes.length ?? 0, `empty svg for ${cat}`).toBeGreaterThan(0);
      expect(svg?.getAttribute("aria-hidden")).toBe("true");
    }
  });

  it("draws a shape for an unknown category instead of crashing", () => {
    const { container } = render(<AqiIcon category="Mystery" />);
    expect(container.querySelector("svg")).not.toBeNull();
  });
});

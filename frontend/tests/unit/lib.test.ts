import { describe, expect, it } from "vitest";
import { searchPlaces } from "../../src/lib/places";
import { CATEGORY_COLORS, categoryIcon, onColor } from "../../src/lib/aqi";

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
      expect(categoryIcon(cat)).not.toBe("?");
      expect(onColor(cat)).toMatch(/^#/);
    }
  });
});

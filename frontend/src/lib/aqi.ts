/** CPCB categories with colorblind-safe colors (always paired with text). */

export const CATEGORY_COLORS: Record<string, string> = {
  Good: "#1a9850",
  Satisfactory: "#91cf60",
  "Moderately Polluted": "#fee08b",
  Poor: "#fc8d59",
  "Very Poor": "#d73027",
  Severe: "#7f0000",
};

export const CATEGORY_ORDER = [
  "Good",
  "Satisfactory",
  "Moderately Polluted",
  "Poor",
  "Very Poor",
  "Severe",
] as const;

/** Dark-enough text color for the given band background. */
export function onColor(category: string): string {
  if (category === "Severe" || category === "Very Poor" || category === "Good") {
    return "#ffffff";
  }
  return "#1f2937";
}

/**
 * Icons accompany colour (WCAG: never colour alone).
 *
 * The previous glyphs were pie wedges (◉ ◔ ◑ ◕) filling up with pollution. Two
 * of them - ◔ and ◕ - read as a loading spinner at a glance, which is the last
 * thing an air-quality reading should look like. These are a severity ramp that
 * cannot be mistaken for a progress indicator: ring, square, triangle, filled
 * square, filled diamond, filled octagon.
 */

export { AqiIcon } from "../components/AqiIcon";

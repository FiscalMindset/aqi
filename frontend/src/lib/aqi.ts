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

export function categoryIcon(category: string): string {
  // icons accompany color (WCAG: never color alone)
  switch (category) {
    case "Good":
      return "◉";
    case "Satisfactory":
      return "◔";
    case "Moderately Polluted":
      return "◑";
    case "Poor":
      return "◕";
    case "Very Poor":
      return "⬤";
    case "Severe":
      return "▲";
    default:
      return "?";
  }
}

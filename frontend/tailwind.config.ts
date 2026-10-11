import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Colorblind-safe CPCB palette (always paired with text/icon in UI)
        aqi: {
          good: "#1a9850",
          satisfactory: "#91cf60",
          moderate: "#fee08b",
          poor: "#fc8d59",
          verypoor: "#d73027",
          severe: "#7f0000",
        },
        night: { 900: "#0b1020", 800: "#111830", 700: "#18213f" },
      },
      minHeight: { touch: "44px" },
      minWidth: { touch: "44px" },
      height: { dvh: "100dvh" },
      fontFamily: {
        sans: ["Inter", "system-ui", "Noto Sans Devanagari", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;

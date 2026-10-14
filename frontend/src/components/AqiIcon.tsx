import type { ReactElement } from "react";

/**
 * AQI category mark as an inline SVG rather than a Unicode geometric glyph.
 *
 * The glyphs (circle, square, triangle) were absent from most system fonts and
 * rendered as tofu boxes, so the category mark a user actually saw beside their
 * PM2.5 value was an empty square carrying no colour and no meaning. SVG is
 * font-independent, scales with zoom, and keeps the icon-plus-text pairing that
 * WCAG 1.4.1 requires. Colour is never the only signal.
 */
export function AqiIcon({
  category,
  className = "h-4 w-4",
}: {
  category: string;
  className?: string;
}): ReactElement {
  const common = {
    className,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
    focusable: false,
  };
  switch (category) {
    case "Good":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M8 12.5l2.5 2.5L16 9.5" />
        </svg>
      );
    case "Satisfactory":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7.5v9M7.5 12h9" />
        </svg>
      );
    case "Moderately Polluted":
      return (
        <svg {...common}>
          <path d="M12 4.5l7.5 14a1 1 0 01-.87 1.5H5.37a1 1 0 01-.87-1.5z" />
          <path d="M12 10v3.6M12 16.2h.01" />
        </svg>
      );
    case "Poor":
      return (
        <svg {...common}>
          <rect x="4.5" y="4.5" width="15" height="15" rx="2.5" />
          <path d="M9.5 9.5l5 5M14.5 9.5l-5 5" />
        </svg>
      );
    case "Very Poor":
      return (
        <svg {...common}>
          <path d="M12 3.5l8.5 15.5H3.5z" />
          <path d="M12 9.5v4M12 16.4h.01" />
        </svg>
      );
    case "Severe":
      return (
        <svg {...common}>
          <path d="M12 3.2l9 16.4H3z" />
          <path d="M12 9v4.4M12 16.4h.01" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
        </svg>
      );
  }
}

export default AqiIcon;

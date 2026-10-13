/**
 * What the air is doing right now.
 *
 * A PM2.5 number on its own does not tell someone why their street is worse
 * than their neighbour's. Wind does: it decides which sources are upstream of
 * you, and how fast pollution disperses. This panel shows the compass the wind
 * is coming from, the arrow it travels, and the ventilation verdict that
 * follows - labelled as derived, because it is inferred from speed rather than
 * measured.
 */

import type { Weather } from "../../lib/api";

function bearing(deg: number): number {
  // Meteorological convention: 0 = wind FROM north. Rotate so the arrow shows
  // where the air is GOING, which is what carries pollution to the user.
  return (deg + 180) % 360;
}

export function WindPanel({ weather }: { weather: Weather | null }) {
  if (!weather) return null;
  const { wind_from_deg: from, wind_from_label: label } = weather;
  const speed = weather.wind_speed_ms;
  const gust = weather.wind_gust_ms;

  return (
    <section
      aria-labelledby="wind-heading"
      data-testid="wind-panel"
      className="rounded-lg border border-line bg-surface-2 p-3"
    >
      <h3 id="wind-heading" className="mb-2 text-sm font-semibold">
        Why here, why now
      </h3>

      <div className="flex items-center gap-4">
        <div
          className="relative h-16 w-16 shrink-0 rounded-full border border-line"
          aria-hidden="true"
        >
          <span className="absolute inset-x-0 top-1 text-center text-[9px] text-muted">N</span>
          <span className="absolute inset-x-0 bottom-1 text-center text-[9px] text-muted">S</span>
          <span className="absolute inset-y-0 left-1 text-[9px] text-muted">W</span>
          <span className="absolute inset-y-0 right-1 text-[9px] text-muted">E</span>
          <svg
            viewBox="0 0 40 40"
            className="absolute inset-2 h-[calc(100%-1rem)] w-[calc(100%-1rem)]"
            role="presentation"
          >
            <g transform={`rotate(${bearing(from ?? 0)} 20 20)`}>
              <path d="M20 6 L26 22 L20 18 L14 22 Z" fill="currentColor" className="text-accent" />
              <line x1="20" y1="18" x2="20" y2="32" stroke="currentColor" strokeWidth="1.5" className="text-accent" />
            </g>
          </svg>
        </div>

        <div className="min-w-0 flex-1 text-sm">
          <p data-testid="wind-summary">
            Wind from the <strong>{label ?? "unknown"}</strong> at{" "}
            <strong>{speed?.toFixed(1)} m/s</strong>
            {gust ? <> (gusting {gust.toFixed(1)})</> : null}
          </p>
          {weather.ventilation && (
            <p className="mt-1 text-muted" data-testid="ventilation">
              Ventilation here is <strong>{weather.ventilation}</strong> —{" "}
              {weather.ventilation_reason}.
            </p>
          )}
          <p className="mt-1 text-xs text-muted">
            {weather.temperature_c != null && <>{weather.temperature_c.toFixed(1)} °C · </>}
            {weather.relative_humidity_pct != null && <>{weather.relative_humidity_pct.toFixed(0)}% humidity · </>}
            {weather.precipitation_mm != null && <>{weather.precipitation_mm.toFixed(1)} mm rain</>}
          </p>
        </div>
      </div>

      <p className="mt-2 text-xs text-muted">
        The arrow shows where the air is travelling. Anything upwind of you can
        reach you; anything downwind cannot. Ventilation is derived from wind
        speed, not measured.
      </p>
    </section>
  );
}

export default WindPanel;
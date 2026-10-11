import { useState } from "react";
import { useTranslation } from "react-i18next";
import { searchPlaces } from "../../lib/places";

export function SearchBox({
  onSelect,
}: {
  onSelect: (lat: number, lon: number) => void;
}) {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const results = searchPlaces(q);

  return (
    <div className="relative">
      <label htmlFor="place-search" className="sr-only">
        {t("explorer.search")}
      </label>
      <div className="flex items-center gap-2 bg-white/10 rounded px-3">
        <span aria-hidden>🔍</span>
        <input
          id="place-search"
          data-testid="search-input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t("explorer.searchPlaceholder")}
          className="bg-transparent w-full py-3 outline-none"
        />
      </div>
      {results.length > 0 && (
        <ul
          role="listbox"
          aria-label={t("explorer.search")}
          className="absolute z-20 mt-1 w-full bg-night-700 rounded shadow-lg"
        >
          {results.map((p) => (
            <li key={p.name}>
              <button
                type="button"
                role="option"
                aria-selected={false}
                onClick={() => {
                  onSelect(p.lat, p.lon);
                  setQ("");
                }}
                className="w-full text-left px-3 py-2 hover:bg-white/10"
              >
                {p.name}
              </button>
            </li>
          ))}
        </ul>
      )}
      <button
        type="button"
        data-testid="use-location"
        className="mt-2 w-full min-h-touch rounded bg-white/10 text-sm"
        onClick={() => {
          if (!navigator.geolocation) return;
          navigator.geolocation.getCurrentPosition(
            (pos) => onSelect(pos.coords.latitude, pos.coords.longitude),
            () => alert(t("explorer.locationDenied")),
          );
        }}
      >
        {t("explorer.useLocation")}
      </button>
    </div>
  );
}

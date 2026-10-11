import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { allPlaces } from "../../lib/places";

const CATEGORIES = [
  "Moderately Polluted",
  "Poor",
  "Very Poor",
  "Severe",
] as const;

export function Subscribe() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [locality, setLocality] = useState("");
  const [threshold, setThreshold] = useState<string>("Poor");
  const [place, setPlace] = useState(allPlaces()[0]);
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [message, setMessage] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!place) return;
    setState("sending");
    try {
      const res = await api.subscribe({
        email,
        locality: locality || place.name,
        lat: place.lat,
        lon: place.lon,
        threshold_category: threshold,
      });
      setState("done");
      setMessage(
        res.status === "already_subscribed"
          ? t("subscribe.idempotent")
          : t("subscribe.success"),
      );
    } catch (err) {
      setState("error");
      setMessage(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="max-w-lg mx-auto p-4 space-y-4 min-w-0">
      <h1 className="text-xl font-bold">{t("subscribe.title")}</h1>
      <p className="text-sm text-slate-400">{t("subscribe.intro")}</p>
      <form className="space-y-3" onSubmit={onSubmit}>
        <label className="block text-sm">
          {t("subscribe.email")}
          <input
            data-testid="sub-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full bg-white/10 rounded p-2 min-h-touch"
          />
        </label>
        <label className="block text-sm">
          {t("subscribe.locality")}
          <input
            data-testid="sub-locality"
            value={locality}
            onChange={(e) => setLocality(e.target.value)}
            placeholder={place?.name}
            className="mt-1 w-full bg-white/10 rounded p-2 min-h-touch"
          />
        </label>
        <label className="block text-sm">
          {t("subscribe.threshold")}
          <select
            data-testid="sub-threshold"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            className="mt-1 w-full bg-white/10 rounded p-2 min-h-touch"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {t(`categories.${c}` as never)}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          {t("routes.from")}
          <select
            value={`${place?.lat},${place?.lon}`}
            onChange={(e) => {
              const [lat, lon] = e.target.value.split(",").map(Number);
              setPlace(allPlaces().find((p) => p.lat === lat && p.lon === lon));
            }}
            className="mt-1 w-full bg-white/10 rounded p-2 min-h-touch"
          >
            {allPlaces().map((p) => (
              <option key={p.name} value={`${p.lat},${p.lon}`}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          data-testid="sub-submit"
          disabled={state === "sending"}
          className="w-full min-h-touch rounded bg-teal-700 hover:bg-teal-600 font-semibold"
        >
          {state === "sending" ? t("subscribe.submitting") : t("subscribe.submit")}
        </button>
        {message && (
          <p
            role={state === "error" ? "alert" : "status"}
            data-testid="sub-message"
            className={state === "error" ? "text-red-300 text-sm" : "text-teal-300 text-sm"}
          >
            {message}
          </p>
        )}
      </form>
    </div>
  );
}

export default Subscribe;

/**
 * Alerts.
 *
 * A subscription form alone is a black box: someone hands over an email address
 * and has no idea what will arrive or when. Two things fix that here.
 *
 * The threshold is chosen as a CPCB band with its actual µg/m³ range, so the
 * choice is about air quality rather than about vocabulary.
 *
 * The alert preview renders the real email against the real data for a chosen
 * point — same template the pipeline sends, same estimate, same sources. You can
 * see exactly what you are signing up for before giving anyone an address.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { allPlaces, type Place } from "../../lib/places";
import { LocationPicker } from "./LocationPicker";

const BANDS = [
  { key: "Moderately Polluted", range: "61 – 90 µg/m³", blurb: "Sensitive groups may notice." },
  { key: "Poor", range: "91 – 120 µg/m³", blurb: "Uncomfortable for everyone." },
  { key: "Very Poor", range: "121 – 250 µg/m³", blurb: "Unhealthy for everyone." },
  { key: "Severe", range: "above 250 µg/m³", blurb: "Hazardous. Act on it." },
] as const;

export function Subscribe() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [locality, setLocality] = useState("");
  const [threshold, setThreshold] = useState<string>("Poor");
  const [place, setPlace] = useState<Place>(allPlaces()[0]!);
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<{ subject: string; html: string } | null>(null);
  const [previewing, setPreviewing] = useState(false);

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

  async function onPreview() {
    if (!place) return;
    setPreviewing(true);
    try {
      const res = await api.previewAlert({
        lat: place.lat,
        lon: place.lon,
        locality: locality || place.name,
        threshold_category: threshold,
      });
      setPreview({ subject: res.subject, html: res.html });
    } catch {
      setPreview(null);
    } finally {
      setPreviewing(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4" data-testid="subscribe">
      <header>
        <h1 className="text-xl font-bold">{t("subscribe.title")}</h1>
        <p className="mt-1 text-sm text-slate-400">{t("subscribe.intro")}</p>
      </header>

      <form className="space-y-4" onSubmit={onSubmit}>
        <label className="block text-sm">
          {t("subscribe.email")}
          <input
            data-testid="sub-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded bg-white/10 p-2 min-h-touch"
          />
        </label>

        <LocationPicker value={place} onChange={setPlace} />
        <label className="block text-sm">
          {t("subscribe.locality")}
          <input
            data-testid="sub-locality"
            value={locality}
            placeholder={place?.name}
            onChange={(e) => setLocality(e.target.value)}
            className="mt-1 w-full rounded bg-white/10 p-2 min-h-touch"
          />
        </label>

        <fieldset>
          <legend className="text-sm">{t("subscribe.threshold")}</legend>
          <p className="mt-0.5 text-xs text-slate-500">
            We send one email when the estimate for this point crosses into this
            band or worse. Bands are the official CPCB categories.
          </p>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {BANDS.map((b) => (
              <label
                key={b.key}
                className={`flex cursor-pointer items-start gap-2 rounded-lg border p-2.5 text-sm ${
                  threshold === b.key
                    ? "border-teal-500/60 bg-teal-500/10"
                    : "border-white/10 bg-slate-900/40"
                }`}
              >
                <input
                  type="radio"
                  name="threshold"
                  value={b.key}
                  checked={threshold === b.key}
                  onChange={() => setThreshold(b.key)}
                  className="mt-1"
                />
                <span>
                  <span className="block font-medium">{b.key}</span>
                  <span className="block font-mono text-[11px] text-slate-400">{b.range}</span>
                  <span className="block text-[11px] text-slate-500">{b.blurb}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="flex flex-wrap gap-2">
          <button
            type="submit"
            data-testid="sub-submit"
            disabled={state === "sending"}
            className="min-h-touch rounded bg-teal-700 px-4 py-2 font-semibold text-white disabled:opacity-60"
          >
            {state === "sending" ? "…" : t("subscribe.submit")}
          </button>
          <button
            type="button"
            data-testid="sub-preview"
            onClick={onPreview}
            disabled={previewing || !place}
            className="min-h-touch rounded border border-white/20 px-4 py-2 text-sm"
          >
            {previewing ? "Rendering…" : "Preview the email"}
          </button>
        </div>

        {state === "done" && (
          <p role="status" data-testid="sub-message" className="rounded bg-emerald-500/10 p-3 text-sm text-emerald-200">
            {message}
          </p>
        )}
        {state === "error" && (
          <p role="alert" data-testid="sub-message" className="rounded bg-rose-500/10 p-3 text-sm text-rose-200">
            {message}
          </p>
        )}
      </form>

      {preview && (
        <section className="rounded-xl border border-white/10 bg-slate-900/40 p-3">
          <h2 className="text-sm font-semibold text-slate-300">The email you would receive</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Subject: {preview.subject}
          </p>
          <div className="mt-2 max-h-[28rem] overflow-auto rounded bg-white p-2">
            <iframe
              title="Alert email preview"
              srcDoc={preview.html}
              className="h-[26rem] w-full border-0"
              sandbox=""
            />
          </div>
        </section>
      )}

      <section className="rounded-xl border border-white/10 bg-slate-900/40 p-4 text-xs leading-relaxed text-slate-400">
        <h2 className="mb-1 text-sm font-semibold text-slate-300">What this is and is not</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Alerts are triggered by <strong>our estimate</strong> for the chosen
            point, not by an official CPCB reading of that exact spot.
          </li>
          <li>
            The threshold bands are CPCB&rsquo;s, defined on 24-hour averages;
            we compare them against an hourly estimate.
          </li>
          <li>
            Every email contains a one-click unsubscribe link. We store your
            address only to send these alerts.
          </li>
          <li>There is no frequency setting yet: at most one email per crossing.</li>
        </ul>
      </section>
    </div>
  );
}

export default Subscribe;
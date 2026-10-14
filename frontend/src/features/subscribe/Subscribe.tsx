/**
 * Alerts.
 *
 * A subscription form alone is a black box: someone hands over an email address
 * and has no idea what will arrive or when. Three things fix that here.
 *
 * The threshold is chosen as a CPCB band with its actual µg/m³ range, so the
 * choice is about air quality rather than vocabulary.
 *
 * The alert preview renders the real email against the real data for the chosen
 * point — same template the pipeline sends, same estimate, same sources.
 *
 * And the current reading for the selected point is shown next to the bands, so
 * it is obvious whether the chosen threshold would have fired today. That is the
 * question people actually have, and answering it makes the form self-explanatory.
 *
 * Layout is a single column on a phone and two columns from `lg`, so the form
 * and the preview sit side by side on a laptop instead of below each other.
 */

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { allPlaces, type Place } from "../../lib/places";
import { LocationPicker } from "./LocationPicker";
import { CATEGORY_ORDER } from "../../lib/aqi";

const BAND_KEYS = [
  "Moderately Polluted",
  "Poor",
  "Very Poor",
  "Severe",
] as const;

export function Subscribe() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [locality, setLocality] = useState("");
  const [localityTouched, setLocalityTouched] = useState(false);
  const [threshold, setThreshold] = useState<string>("Poor");
  const [place, setPlace] = useState<Place>(allPlaces()[0]!);
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<{ subject: string; html: string } | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [current, setCurrent] = useState<{ mid: number; band: string } | null>(null);

  // Fill the label in for the user. Reported confusion was "why do I still have
  // to type a place when I just tapped Use my current location" — the field was
  // empty with only a placeholder, so it read as mandatory. Anything the user
  // types themselves is never overwritten.
  useEffect(() => {
    if (!localityTouched) setLocality(place.name);
  }, [place.name, localityTouched]);

  useEffect(() => {
    let cancelled = false;
    api
      .estimate(place.lat, place.lon)
      .then((e) => {
        if (!cancelled) setCurrent({ mid: e.pm25_mid, band: e.category });
      })
      .catch(() => {
        if (!cancelled) setCurrent(null);
      });
    return () => {
      cancelled = true;
    };
  }, [place.lat, place.lon]);

  const label = locality.trim() || place.name;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setState("sending");
    try {
      const res = await api.subscribe({
        email,
        locality: label,
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
    setPreviewing(true);
    try {
      const res = await api.previewAlert({
        lat: place.lat,
        lon: place.lon,
        locality: label,
        threshold_category: threshold,
      });
      setPreview({ subject: res.subject, html: res.html });
    } catch {
      setPreview(null);
    } finally {
      setPreviewing(false);
    }
  }

  // Does the chosen threshold already sit below the current reading? If so the
  // user would get an alert immediately, which should be visible before they
  // subscribe rather than discovered in their inbox.
  // Both values are CPCB category names; a band we do not know about must not
  // silently read as "below the threshold" and hide a crossing.
  const rank = (c: string): number => {
    const i = CATEGORY_ORDER.indexOf(c as (typeof CATEGORY_ORDER)[number]);
    return i < 0 ? Number.POSITIVE_INFINITY : i;
  };
  const wouldFireNow =
    current !== null && rank(current.band) >= rank(threshold);

  return (
    <div className="mx-auto max-w-6xl space-y-5 p-4" data-testid="subscribe">
      <header>
        <h1 className="text-xl font-bold sm:text-2xl">{t("subscribe.title")}</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-400">{t("subscribe.intro")}</p>
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start">
        <form className="space-y-5" onSubmit={onSubmit} noValidate>
          <section>
            <label className="block text-sm font-medium" htmlFor="sub-email">
              {t("subscribe.email")}
            </label>
            <input
              id="sub-email"
              data-testid="sub-email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded bg-white/10 p-2.5 min-h-touch"
            />
            <p className="mt-1 text-xs text-slate-500">{t("subscribe.emailHint")}</p>
          </section>

          <section>
            <h2 className="text-sm font-medium">{t("subscribe.pickFirst")}</h2>
            <p className="mt-0.5 text-xs text-slate-500">{t("subscribe.pickHint")}</p>
            <div className="mt-2">
              <LocationPicker
                value={place}
                onChange={(p) => {
                  setPlace(p);
                  setState("idle");
                }}
              />
            </div>
          </section>

          <section>
            <label className="block text-sm font-medium" htmlFor="sub-locality">
              {t("subscribe.locality")}
            </label>
            <input
              id="sub-locality"
              data-testid="sub-locality"
              value={locality}
              onChange={(e) => {
                setLocalityTouched(true);
                setLocality(e.target.value);
              }}
              className="mt-1 w-full rounded bg-white/10 p-2.5 min-h-touch"
            />
            <p className="mt-1 text-xs text-slate-500">{t("subscribe.localityHint")}</p>
          </section>

          <fieldset>
            <legend className="text-sm font-medium">{t("subscribe.threshold")}</legend>
            <p className="mt-0.5 text-xs text-slate-500">
              {t("subscribe.thresholdHint")}
            </p>

            {current && (
              <p
                data-testid="sub-current"
                className="mt-2 rounded-lg bg-slate-800/60 px-3 py-2 text-xs text-slate-300"
              >
                {t("subscribe.current")}:{" "}
                <span className="font-mono text-slate-100">
                  {current.mid.toFixed(0)} µg/m³
                </span>{" "}
                <span className="text-slate-400">({current.band})</span>
                {wouldFireNow && (
                  <span className="ml-1 text-amber-300">
                    — {t("subscribe.willFire")}
                  </span>
                )}
              </p>
            )}

            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {BAND_KEYS.map((key) => {
                const b = t(`subscribe.bands.${key}.range`);
                const blurb = t(`subscribe.bands.${key}.blurb`);
                return (
                  <label
                    key={key}
                    className={`flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-sm transition-colors ${
                      threshold === key
                        ? "border-teal-500/60 bg-teal-500/10"
                        : "border-white/10 bg-slate-900/40 hover:border-white/25"
                    }`}
                  >
                    <input
                      type="radio"
                      name="threshold"
                      value={key}
                      checked={threshold === key}
                      onChange={() => setThreshold(key)}
                      className="mt-1 h-4 w-4 shrink-0"
                    />
                    <span className="min-w-0">
                      <span className="block font-medium">{key}</span>
                      <span className="block font-mono text-[11px] text-slate-400">
                        {b}
                      </span>
                      <span className="mt-0.5 block text-[11px] leading-snug text-slate-500">
                        {blurb}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          <div className="flex flex-wrap gap-2">
            <button
              type="submit"
              data-testid="sub-submit"
              disabled={state === "sending"}
              className="min-h-touch flex-1 rounded bg-teal-700 px-4 py-2.5 font-semibold text-white hover:bg-teal-600 disabled:opacity-60 sm:flex-none"
            >
              {state === "sending" ? t("subscribe.submitting") : t("subscribe.submit")}
            </button>
            <button
              type="button"
              data-testid="sub-preview"
              onClick={onPreview}
              disabled={previewing}
              className="min-h-touch rounded border border-white/20 px-4 py-2.5 text-sm hover:bg-white/5 disabled:opacity-60"
            >
              {previewing ? t("subscribe.previewing") : t("subscribe.preview")}
            </button>
          </div>

          {state === "done" && (
            <p
              role="status"
              data-testid="sub-message"
              className="rounded bg-emerald-500/10 p-3 text-sm text-emerald-200"
            >
              {message}
            </p>
          )}
          {state === "error" && (
            <p
              role="alert"
              data-testid="sub-message"
              className="rounded bg-rose-500/10 p-3 text-sm text-rose-200"
            >
              {message}
            </p>
          )}
        </form>

        <div className="space-y-4 lg:sticky lg:top-20">
          {preview ? (
            <section className="rounded-xl border border-white/10 bg-slate-900/40 p-3">
              <h2 className="text-sm font-semibold text-slate-300">
                {t("subscribe.previewTitle")}
              </h2>
              <p className="mt-0.5 break-words text-xs text-slate-500">
                {preview.subject}
              </p>
              <div className="mt-2 overflow-hidden rounded bg-white">
                <iframe
                  title={t("subscribe.previewTitle")}
                  srcDoc={preview.html}
                  className="h-[28rem] w-full border-0"
                  sandbox=""
                />
              </div>
            </section>
          ) : (
            <section className="rounded-xl border border-white/10 bg-slate-900/40 p-4 text-xs leading-relaxed text-slate-400">
              <h2 className="mb-2 text-sm font-semibold text-slate-300">
                {t("subscribe.honestTitle")}
              </h2>
              <ul className="list-disc space-y-2 pl-5">
                <li>{t("subscribe.honestModel")}</li>
                <li>{t("subscribe.honestWindow")}</li>
                <li>{t("subscribe.honestPrivacy")}</li>
                <li>{t("subscribe.honestRate")}</li>
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

export default Subscribe;
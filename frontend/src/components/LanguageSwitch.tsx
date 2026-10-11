import { useTranslation } from "react-i18next";

const LANGS = [
  { code: "en", label: "EN" },
  { code: "hi", label: "हिं" },
] as const;

/** Language switch; persists the choice (rule: language switch persists). */
export function LanguageSwitch() {
  const { i18n } = useTranslation();
  return (
    <div role="group" aria-label="Language" className="flex rounded overflow-hidden border border-white/20">
      {LANGS.map((l) => (
        <button
          key={l.code}
          type="button"
          data-testid={`lang-${l.code}`}
          aria-pressed={i18n.resolvedLanguage === l.code}
          onClick={() => void i18n.changeLanguage(l.code)}
          className={[
            "px-3 min-h-touch min-w-touch text-xs font-semibold",
            i18n.resolvedLanguage === l.code ? "bg-teal-700 text-white" : "text-slate-300",
          ].join(" ")}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}

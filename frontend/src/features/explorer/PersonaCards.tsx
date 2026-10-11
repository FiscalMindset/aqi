import { useTranslation } from "react-i18next";
import type { Advice } from "../../lib/api";

/** Persona advice cards: parent / rider / worker / general. */
export function PersonaCards({ advice }: { advice: Advice[] }) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="personas-heading" data-testid="persona-cards">
      <h3 id="personas-heading" className="font-semibold">
        {t("explorer.personas")}
      </h3>
      <div className="grid grid-cols-1 gap-2 mt-2">
        {advice.map((a) => (
          <article key={a.persona} className="rounded bg-white/5 p-3">
            <h4 className="text-sm font-semibold text-teal-300">
              {t(`personas.${a.persona}` as never)}
            </h4>
            <p className="text-sm mt-1">{a.headline}</p>
            <ul className="text-xs text-slate-400 mt-1 list-disc pl-4">
              {a.actions.map((action, i) => (
                <li key={i}>{action}</li>
              ))}
            </ul>
            <p className="text-[11px] text-slate-400 mt-1">{a.disclaimer}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

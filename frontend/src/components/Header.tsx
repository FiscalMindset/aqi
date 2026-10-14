import { useTranslation } from "react-i18next";
import { Link, NavLink } from "react-router-dom";
import { LanguageSwitch } from "./LanguageSwitch";

const NAV = [
  { to: "/", key: "nav.explorer", end: true },
  { to: "/routes", key: "nav.routes", end: false },
  { to: "/how-it-works", key: "nav.how", end: false },
  { to: "/methodology", key: "nav.method", end: false },
  { to: "/algorithm", key: "nav.algorithm", end: false },
  { to: "/status", key: "nav.status", end: false },
  { to: "/subscribe", key: "nav.subscribe", end: false },
];

export function Header() {
  const { t } = useTranslation();
  return (
    <header className="sticky top-0 z-30 bg-night-800/95 backdrop-blur border-b border-white/10">
      <div className="mx-auto max-w-7xl px-4 h-14 flex items-center gap-4">
        <Link
          to="/"
          className="font-bold text-lg tracking-tight px-2 py-2 min-h-touch flex items-center"
          aria-label={t("app.name")}
        >
          {t("app.name")}
        </Link>
        <nav aria-label="Primary" className="hidden md:flex gap-1 flex-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                [
                  "px-3 py-2 rounded text-sm min-h-touch flex items-center",
                  isActive ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5",
                ].join(" ")
              }
            >
              {t(item.key)}
            </NavLink>
          ))}
        </nav>
        <LanguageSwitch />
      </div>
      <nav aria-label="Primary mobile" className="md:hidden flex overflow-x-auto gap-1 px-2 pb-2">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              [
                "px-3 py-2 rounded text-sm whitespace-nowrap min-h-touch flex items-center",
                isActive ? "bg-white/10 text-white" : "text-slate-300",
              ].join(" ")
            }
          >
            {t(item.key)}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}

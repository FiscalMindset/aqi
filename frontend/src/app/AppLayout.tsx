import { Outlet } from "react-router-dom";
import { DemoBanner } from "../components/DemoBanner";
import { Header } from "../components/Header";
import { OfflineBanner } from "../components/OfflineBanner";
import { SkipLink } from "../components/SkipLink";

/** App shell: skip link, header, offline + demo banners, routed content. */
export function AppLayout() {
  return (
    <div className="min-h-dvh flex flex-col bg-night-900 text-slate-100">
      <SkipLink />
      <Header />
      <OfflineBanner />
      <DemoBanner />
      <main id="main" className="flex-1" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="px-4 py-3 text-xs text-slate-400 border-t border-white/10">
        <span>
          Estimates, not measurements. Station data via OpenAQ (CC BY 4.0); map
          data © OpenStreetMap contributors (ODbL); weather © Open-Meteo.
        </span>
      </footer>
    </div>
  );
}

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

/** Offline banner: the PWA keeps the shell alive; users must know it is stale. */
export function OfflineBanner() {
  const { t } = useTranslation();
  const [online, setOnline] = useState(navigator.onLine);

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  if (online) return null;
  return (
    <div
      role="status"
      data-testid="offline-banner"
      className="w-full bg-slate-700 text-slate-100 text-center text-sm py-2 px-3"
    >
      {t("offline.banner")}
    </div>
  );
}

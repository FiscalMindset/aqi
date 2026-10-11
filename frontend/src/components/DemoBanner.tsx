import { useTranslation } from "react-i18next";
import { useEffect, useState } from "react";

/**
 * Permanent, visible demo banner (rule 1). Renders whenever the API reports
 * demo data (X-Dhuan-Demo response header) or DEMO_MODE is built in.
 */
export function DemoBanner() {
  const { t } = useTranslation();
  const [demo, setDemo] = useState(false);

  useEffect(() => {
    const handler = () => setDemo(document.documentElement.dataset.demo === "1");
    handler();
    const observer = new MutationObserver(handler);
    observer.observe(document.documentElement, { attributes: true });
    return () => observer.disconnect();
  }, []);

  if (!demo) return null;
  return (
    <div
      role="alert"
      data-testid="demo-banner"
      className="w-full bg-amber-400 text-amber-950 text-center text-sm font-semibold py-2 px-3"
    >
      {t("demo.banner")}
    </div>
  );
}

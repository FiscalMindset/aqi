import { useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

type Level = "peek" | "half" | "full";

const HEIGHTS: Record<Level, string> = {
  peek: "26dvh",
  half: "55dvh",
  full: "92dvh",
};

/**
 * Draggable bottom sheet for mobile (peek / half / full).
 * Pointer drag between levels; respects safe-area insets via env().
 */
export function BottomSheet({
  full,
  peek,
  children,
}: {
  full: boolean;
  peek: ReactNode;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const startY = useRef<number | null>(null);
  const [level, setLevel] = useState<Level>(full ? "half" : "peek");
  const effective: Level = full ? "full" : level;

  function onPointerDown(e: React.PointerEvent) {
    startY.current = e.clientY;
  }

  function onPointerUp(e: React.PointerEvent) {
    if (startY.current === null) return;
    const dy = e.clientY - startY.current;
    if (dy < -40) setLevel((l) => (l === "peek" ? "half" : "full"));
    if (dy > 40) setLevel((l) => (l === "full" ? "half" : "peek"));
    startY.current = null;
  }

  return (
    <section
      aria-label="Results"
      data-testid="bottom-sheet"
      className="rounded-t-2xl bg-night-800 shadow-2xl border-t border-white/10 flex flex-col overflow-hidden"
      style={{
        height: HEIGHTS[effective],
        paddingBottom: "env(safe-area-inset-bottom)",
      }}
    >
      <button
        type="button"
        aria-label={t("app.name")}
        onClick={() => (effective === "full" ? setLevel("half") : setLevel("full"))}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        className="w-full min-h-touch py-2 touch-none flex items-center justify-center"
      >
        <span className="mx-auto block h-1.5 w-10 rounded-full bg-white/40" />
        <span className="sr-only">{t("app.name")}</span>
      </button>
      <div className="flex-1 overflow-y-auto">
        {peek}
        {effective !== "peek" && children}
      </div>
    </section>
  );
}

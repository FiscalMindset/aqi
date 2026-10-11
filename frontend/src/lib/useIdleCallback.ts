import { useEffect } from "react";

/** Run `cb` when the browser is idle (falls back to a 200ms timeout). */
export function useIdleCallback(cb: () => void): void {
  useEffect(() => {
    const w = window as unknown as {
      requestIdleCallback?: (fn: () => void, opts?: { timeout: number }) => void;
    };
    let timeout: ReturnType<typeof setTimeout> | undefined;
    if (w.requestIdleCallback) {
      w.requestIdleCallback(cb, { timeout: 500 });
    } else {
      timeout = setTimeout(cb, 200);
    }
    return () => {
      if (timeout !== undefined) clearTimeout(timeout);
    };
  }, [cb]);
}

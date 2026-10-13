/**
 * Detect a stale service worker and get rid of it.
 *
 * What went wrong: an older deploy precached `index.html`, the service worker
 * served it cache-first, and the page booted into a bundle from a previous
 * release. That bundle called `/v1/estimate`, which the gateway does not serve
 * under this stage, so every request 403'd and the app showed "Could not load
 * the estimate" with no way for the user to tell that the fix was already live.
 *
 * Three layers, because any one of them can be the one that fails:
 *
 * 1. On load, ask the server what the current build is. If it differs from the
 *    bundle that is running, unregister every service worker, drop the caches
 *    and reload - once, guarded by sessionStorage so it cannot loop.
 * 2. Listen for a waiting worker and activate it immediately, so an update
 *    never sits in limbo behind an open tab.
 * 3. If registration fails outright, keep working online rather than dying.
 */

const VERSION_URL = `${import.meta.env.BASE_URL}version.json`;
const RELOAD_FLAG = "dhuan:stale-reload";

export async function refreshIfStale(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  try {
    const response = await fetch(`${VERSION_URL}?t=${Date.now()}`, {
      cache: "no-store",
    });
    if (!response.ok) return;
    const served = (await response.json()) as { build?: string };
    const running = import.meta.env.VITE_BUILD_ID;
    if (!served.build || !running || served.build === running) return;
    if (sessionStorage.getItem(RELOAD_FLAG) === served.build) return;
    sessionStorage.setItem(RELOAD_FLAG, served.build);
    await clearEverything();
  } catch {
    // Offline, or the version file is unreachable: leave the app alone. The
    // precached shell is exactly what this is for.
  }
}

export async function clearEverything(): Promise<void> {
  try {
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.map((r) => r.unregister()));
  } catch {
    /* nothing we can do */
  }
  try {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
  } catch {
    /* nothing we can do */
  }
  window.location.reload();
}

export function watchForUpdates(): void {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    // A new worker took over; reload once so the page runs its code.
    if (sessionStorage.getItem(RELOAD_FLAG)) return;
    sessionStorage.setItem(RELOAD_FLAG, "controllerchange");
    window.location.reload();
  });
}
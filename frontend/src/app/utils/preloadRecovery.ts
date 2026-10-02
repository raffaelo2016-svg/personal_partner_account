const LAST_RELOAD_KEY = 'uritech:last-preload-error-reload';
const RELOAD_COOLDOWN_MS = 10_000;

interface PreloadRecoveryOptions {
  reload?: () => void;
  now?: () => number;
  storage?: Pick<Storage, 'getItem' | 'setItem'>;
  target?: Pick<Window, 'addEventListener' | 'removeEventListener'>;
}

/**
 * Vite emits `vite:preloadError` when a lazy-loaded chunk is no longer
 * available, most commonly because a new deployment replaced the build.
 * Reload once so the browser receives the current index and chunk names.
 */
export function installPreloadErrorRecovery(options: PreloadRecoveryOptions = {}) {
  const target = options.target ?? window;
  const storage = options.storage ?? window.sessionStorage;
  const reload = options.reload ?? (() => window.location.reload());
  const now = options.now ?? Date.now;

  const handlePreloadError = (event: Event) => {
    event.preventDefault();

    let lastReloadAt: number;
    try {
      lastReloadAt = Number(storage.getItem(LAST_RELOAD_KEY)) || 0;
    } catch {
      // Without a reload guard a blocked storage API could create a loop.
      return;
    }

    const currentTime = now();
    if (currentTime - lastReloadAt < RELOAD_COOLDOWN_MS) return;

    try {
      storage.setItem(LAST_RELOAD_KEY, String(currentTime));
    } catch {
      return;
    }

    reload();
  };

  target.addEventListener('vite:preloadError', handlePreloadError);
  return () => target.removeEventListener('vite:preloadError', handlePreloadError);
}

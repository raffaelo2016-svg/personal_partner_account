import { afterEach, describe, expect, it, vi } from 'vitest';
import { installPreloadErrorRecovery } from './preloadRecovery';

describe('installPreloadErrorRecovery', () => {
  afterEach(() => {
    window.sessionStorage.clear();
  });

  it('reloads once when a lazy chunk cannot be loaded', () => {
    const reload = vi.fn();
    const uninstall = installPreloadErrorRecovery({ reload, now: () => 20_000 });

    const firstError = new Event('vite:preloadError', { cancelable: true });
    window.dispatchEvent(firstError);
    window.dispatchEvent(new Event('vite:preloadError', { cancelable: true }));

    expect(firstError.defaultPrevented).toBe(true);
    expect(reload).toHaveBeenCalledTimes(1);
    uninstall();
  });

  it('allows another recovery attempt after the cooldown', () => {
    const reload = vi.fn();
    let currentTime = 20_000;
    const uninstall = installPreloadErrorRecovery({ reload, now: () => currentTime });

    window.dispatchEvent(new Event('vite:preloadError', { cancelable: true }));
    currentTime += 10_000;
    window.dispatchEvent(new Event('vite:preloadError', { cancelable: true }));

    expect(reload).toHaveBeenCalledTimes(2);
    uninstall();
  });
});

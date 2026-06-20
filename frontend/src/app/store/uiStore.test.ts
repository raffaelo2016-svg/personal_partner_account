import { afterEach, describe, expect, it, vi } from 'vitest';
import { useUIStore } from './uiStore';

const INITIAL = { sidebarOpen: true };

afterEach(() => {
  useUIStore.setState(INITIAL);
});

describe('useUIStore', () => {
  it('по умолчанию sidebar открыт', () => {
    expect(useUIStore.getState().sidebarOpen).toBe(true);
  });

  it('toggleSidebar переключает состояние', () => {
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarOpen).toBe(false);

    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarOpen).toBe(true);
  });

  it('setSidebarOpen(false) закрывает', () => {
    useUIStore.getState().setSidebarOpen(false);
    expect(useUIStore.getState().sidebarOpen).toBe(false);
  });

  it('setSidebarOpen(true) открывает', () => {
    useUIStore.setState({ sidebarOpen: false });
    useUIStore.getState().setSidebarOpen(true);
    expect(useUIStore.getState().sidebarOpen).toBe(true);
  });

  it('setSidebarOpen с текущим значением не ломает состояние', () => {
    useUIStore.getState().setSidebarOpen(true);
    expect(useUIStore.getState().sidebarOpen).toBe(true);
  });

  it('уведомляет подписчиков при изменении', () => {
    const listener = vi.fn();
    const unsub = useUIStore.subscribe(listener);

    useUIStore.getState().toggleSidebar();
    useUIStore.getState().setSidebarOpen(true);

    expect(listener).toHaveBeenCalledTimes(2);
    unsub();
  });

  it('отписанный слушатель не вызывается', () => {
    const listener = vi.fn();
    const unsub = useUIStore.subscribe(listener);
    unsub();
    useUIStore.getState().toggleSidebar();
    expect(listener).not.toHaveBeenCalled();
  });
});

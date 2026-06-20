import { renderHook } from '@testing-library/react';
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useIntersectionObserver } from './useIntersectionObserver';

type IOCallback = (entries: IntersectionObserverEntry[]) => void;

interface MockObserver {
  callback: IOCallback;
  options: IntersectionObserverInit | undefined;
  observe: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
  unobserve: ReturnType<typeof vi.fn>;
  trigger: (isIntersecting: boolean) => void;
}

let observers: MockObserver[] = [];

class MockIntersectionObserver implements Partial<IntersectionObserver> {
  callback: IOCallback;
  options: IntersectionObserverInit | undefined;
  observe = vi.fn();
  disconnect = vi.fn();
  unobserve = vi.fn();
  constructor(cb: IOCallback, options?: IntersectionObserverInit) {
    this.callback = cb;
    this.options = options;
    observers.push({
      callback: cb,
      options,
      observe: this.observe,
      disconnect: this.disconnect,
      unobserve: this.unobserve,
      trigger: (isIntersecting: boolean) =>
        cb([{ isIntersecting } as IntersectionObserverEntry]),
    });
  }
}

beforeEach(() => {
  observers = [];
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useIntersectionObserver', () => {
  it('возвращает ref', () => {
    const { result } = renderHook(() =>
      useIntersectionObserver(() => {}, false),
    );
    expect(result.current).toHaveProperty('current');
  });

  it('не создаёт observer при enabled=false', () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useIntersectionObserver(cb, false));
    act(() => {
      result.current.current = document.createElement('div');
    });
    expect(observers.length).toBe(0);
  });

  it('не создаёт observer пока ref не установлен', () => {
    renderHook(() => useIntersectionObserver(() => {}, true));
    expect(observers.length).toBe(0);
  });

  it('создаёт observer при enabled=true и установленном ref', () => {
    const cb = vi.fn();
    const el = document.createElement('div');
    const { rerender, result } = renderHook(
      ({ enabled }: { enabled: boolean }) => useIntersectionObserver(cb, enabled),
      { initialProps: { enabled: false } },
    );
    act(() => {
      result.current.current = el;
    });
    rerender({ enabled: true });

    expect(observers.length).toBe(1);
    expect(observers[0].options).toEqual({ threshold: 0.1 });
    expect(observers[0].observe).toHaveBeenCalledWith(el);
  });

  it('вызывает callback при пересечении', () => {
    const cb = vi.fn();
    const el = document.createElement('div');
    const { rerender, result } = renderHook(
      ({ enabled }: { enabled: boolean }) => useIntersectionObserver(cb, enabled),
      { initialProps: { enabled: false } },
    );
    act(() => {
      result.current.current = el;
    });
    rerender({ enabled: true });

    observers[0].trigger(true);
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it('не вызывает callback если isIntersecting=false', () => {
    const cb = vi.fn();
    const el = document.createElement('div');
    const { rerender, result } = renderHook(
      ({ enabled }: { enabled: boolean }) => useIntersectionObserver(cb, enabled),
      { initialProps: { enabled: false } },
    );
    act(() => {
      result.current.current = el;
    });
    rerender({ enabled: true });

    observers[0].trigger(false);
    expect(cb).not.toHaveBeenCalled();
  });

  it('вызывает disconnect при размонтировании', () => {
    const cb = vi.fn();
    const el = document.createElement('div');
    const { rerender, result, unmount } = renderHook(
      ({ enabled }: { enabled: boolean }) => useIntersectionObserver(cb, enabled),
      { initialProps: { enabled: false } },
    );
    act(() => {
      result.current.current = el;
    });
    rerender({ enabled: true });

    unmount();
    expect(observers[0].disconnect).toHaveBeenCalled();
  });

  it('пересоздаёт observer при смене callback', () => {
    const cb1 = vi.fn();
    const cb2 = vi.fn();
    const el = document.createElement('div');
    const { rerender, result } = renderHook(
      ({ cb, enabled }: { cb: () => void; enabled: boolean }) =>
        useIntersectionObserver(cb, enabled),
      { initialProps: { cb: cb1, enabled: false } },
    );
    act(() => {
      result.current.current = el;
    });
    rerender({ cb: cb1, enabled: true });
    expect(observers.length).toBe(1);

    rerender({ cb: cb2, enabled: true });
    expect(observers.length).toBe(2);
    expect(observers[0].disconnect).toHaveBeenCalled();
  });
});

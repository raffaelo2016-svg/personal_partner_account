import '@testing-library/jest-dom/vitest';

// Node 26 объявляет experimental-хранилище `localStorage`, которое без флага
// --localstorage-file остаётся undefined. Vitest в jsdom-окружении из-за этого
// не оставляет тестам рабочего localStorage, хотя в браузере он есть.
// Для тестов достаточно простой in-memory реализации.
if (!globalThis.localStorage) {
  const store = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key) => (store.has(key) ? store.get(key)! : null),
    key: (index) => Array.from(store.keys())[index] ?? null,
    removeItem: (key) => {
      store.delete(key);
    },
    setItem: (key, value) => {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(globalThis, 'localStorage', { value: storage, configurable: true });
  if (typeof window !== 'undefined' && window !== globalThis) {
    Object.defineProperty(window, 'localStorage', { value: storage, configurable: true });
  }
}

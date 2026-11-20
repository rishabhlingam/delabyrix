/**
 * Vitest setup file — runs before all tests.
 * Extends expect with @testing-library/jest-dom matchers.
 */
import "@testing-library/jest-dom/vitest";

// Mock localStorage for i18n
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = String(value); },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();

Object.defineProperty(window, "localStorage", { value: localStorageMock });

// Silence console.error for expected test noise (react act warnings etc.)
const originalError = console.error;
beforeEach(() => {
  console.error = (...args: unknown[]) => {
    // suppress act() warnings from RTL
    if (typeof args[0] === "string" && args[0].includes("Warning:")) return;
    originalError(...args);
  };
});
afterEach(() => {
  console.error = originalError;
});

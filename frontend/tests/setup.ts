import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";

// Restore mocked fetch after each test to prevent Node/undici
// "invalid onError method" errors when vi.stubGlobal("fetch", ...)
// replaces native fetch with an incompatible mock object.
const originalFetch = globalThis.fetch;
afterEach(() => {
  if (globalThis.fetch !== originalFetch) {
    vi.stubGlobal("fetch", originalFetch);
  }
});

// Canonical browser-path shape (assfix 2026-10-07, CORS 1F):
// same-origin relative by default (vite proxies /api + /mcp to the backend),
// absolute backend URL ONLY when running inside the Tauri WebView (no proxy).
function isTauri(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as Record<string, unknown>;
  return w.__TAURI__ !== undefined || w.__TAURI_INTERNALS__ !== undefined;
}

const API_BASE = isTauri() ? "http://127.0.0.1:10946" : "";

export function apiFetch(
  path: string,
  options?: RequestInit,
): Promise<Response> {
  return fetch(`${API_BASE}${path}`, options);
}

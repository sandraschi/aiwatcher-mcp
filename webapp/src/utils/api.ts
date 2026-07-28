const API_BASE = "http://127.0.0.1:10946";

export function apiFetch(
  path: string,
  options?: RequestInit,
): Promise<Response> {
  return fetch(`${API_BASE}${path}`, options);
}

const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
const TOKEN_KEY = 'careerpilot_access_token';
// Per-tab storage limits persistence; this is still accessible to JavaScript and vulnerable to XSS.
export function getAccessToken(): string | null { return sessionStorage.getItem(TOKEN_KEY); }
export function setAccessToken(token: string | null): void {
  if (token) sessionStorage.setItem(TOKEN_KEY, token); else sessionStorage.removeItem(TOKEN_KEY);
}
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = 'ApiError'; }
}
export async function apiRequest<T>(path: string, init: RequestInit = {}, authenticated = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (authenticated) {
    const token = getAccessToken();
    if (!token) throw new ApiError(401, 'Please log in to continue.');
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  let response: Response;
  try { response = await fetch(`${base}${path}`, { ...init, headers }); }
  catch { throw new ApiError(0, 'Could not reach the backend. Check that it is running.'); }
  if (!response.ok) {
    if (response.status === 401 && authenticated) { setAccessToken(null); window.dispatchEvent(new Event('careerpilot:session-expired')); }
    let message = 'The request could not be completed.';
    try { const body = await response.json(); if (typeof body.detail === 'string') message = body.detail; else if (response.status === 422) message = 'Please check your information and try again.'; } catch { /* no JSON body */ }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

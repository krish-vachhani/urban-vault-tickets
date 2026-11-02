import axios from "axios";

import { API_BASE_URL } from "./apiConfig";

/**
 * Everything the Axios layer needs to know about the signed-in session:
 * the in-memory access token, the CSRF token, and the single-flight refresh.
 * See README-authentication §3 and README-frontend-architecture §13.
 */

/**
 * Client for the auth endpoints (csrf, login, refresh, logout). It has no Bearer
 * header and no refresh-on-401 interceptor, so these calls can never trigger
 * the refresh logic recursively.
 */
export const authClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

// --- Access token (memory only: never localStorage, sessionStorage, or a URL) ---

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

// --- CSRF token ---

type CsrfResponse = { csrf_token: string };

let csrfTokenRequest: Promise<string> | null = null;

/** Fetches the CSRF token once (also sets Django's CSRF cookie) and reuses it afterwards. */
export function getCsrfToken(): Promise<string> {
  csrfTokenRequest ??= authClient
    .get<CsrfResponse>("/auth/csrf/")
    .then((response) => response.data.csrf_token)
    .catch((error: unknown) => {
      csrfTokenRequest = null; // allow a later attempt to try again
      throw error;
    });
  return csrfTokenRequest;
}

// --- Single-flight refresh ---

type RefreshResponse = { access: string };

let refreshInFlight: Promise<string> | null = null;

async function requestNewAccessToken(): Promise<string> {
  const csrfToken = await getCsrfToken();
  const response = await authClient.post<RefreshResponse>("/auth/refresh/", undefined, {
    headers: { "X-CSRFToken": csrfToken },
  });
  setAccessToken(response.data.access);
  return response.data.access;
}

/**
 * Exchanges the HttpOnly refresh cookie for a new access token. Callers that
 * arrive while a refresh is running share it: the refresh token rotates on
 * every use, so two parallel refreshes would invalidate each other.
 */
export function refreshAccessToken(): Promise<string> {
  refreshInFlight ??= requestNewAccessToken().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

// --- Terminal authentication failure ---

let authenticationFailureHandler: () => void = () => {};

/** The auth provider registers how to end the session when refreshing is no longer possible. */
export function setAuthenticationFailureHandler(handler: () => void): void {
  authenticationFailureHandler = handler;
}

export function notifyAuthenticationFailure(): void {
  authenticationFailureHandler();
}

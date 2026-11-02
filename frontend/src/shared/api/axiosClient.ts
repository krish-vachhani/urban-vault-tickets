import axios, { isAxiosError, type InternalAxiosRequestConfig } from "axios";

import { API_BASE_URL } from "./apiConfig";
import { getAccessToken, notifyAuthenticationFailure, refreshAccessToken } from "./authSession";

const HTTP_UNAUTHORIZED = 401;

type RetryableRequestConfig = InternalAxiosRequestConfig & { hasRetriedAfterRefresh?: boolean };

/**
 * The single Axios instance used for every protected API call.
 *
 * Requests go to the same origin (the Vite proxy locally, CloudFront in
 * production). The request interceptor attaches the in-memory access token; the
 * response interceptor refreshes it once when the API answers 401.
 */
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  // Send cookies (the HttpOnly refresh token) with same-origin requests.
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  const accessToken = getAccessToken();
  if (accessToken) {
    config.headers.set("Authorization", `Bearer ${accessToken}`);
  }
  return config;
});

apiClient.interceptors.response.use(undefined, async (error: unknown) => {
  if (!isAxiosError(error) || error.response?.status !== HTTP_UNAUTHORIZED || !error.config) {
    throw error;
  }
  const failedRequest: RetryableRequestConfig = error.config;

  // A request is retried at most once. A 401 on the retry means the account
  // itself is no longer allowed in, so the session ends.
  if (failedRequest.hasRetriedAfterRefresh) {
    notifyAuthenticationFailure();
    throw error;
  }
  failedRequest.hasRetriedAfterRefresh = true;

  // A late 401 for a token that has since been replaced does not need another refresh.
  const tokenSentWithRequest = failedRequest.headers.get("Authorization");
  const tokenIsStale = typeof tokenSentWithRequest === "string" && tokenSentWithRequest !== `Bearer ${getAccessToken()}`;

  if (!tokenIsStale) {
    try {
      await refreshAccessToken();
    } catch {
      notifyAuthenticationFailure();
      throw error;
    }
  }

  // The request interceptor attaches the new token when the request is resent.
  return apiClient.request(failedRequest);
});

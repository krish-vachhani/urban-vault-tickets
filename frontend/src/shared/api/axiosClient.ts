import axios from "axios";

const DEFAULT_API_BASE_URL = "/api/v1";

/**
 * The single Axios instance used for every API call.
 *
 * Requests go to the same origin (the Vite proxy locally, CloudFront in
 * production). Bearer-token attachment, CSRF headers, and the single-flight
 * token refresh are added with the authentication feature.
 */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  // Send cookies (the HttpOnly refresh token) with same-origin auth requests.
  withCredentials: true,
});

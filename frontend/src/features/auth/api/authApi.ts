import { apiClient } from "../../../shared/api/axiosClient";
import { authClient, getCsrfToken } from "../../../shared/api/authSession";
import type { CurrentUser, LoginCredentials, LoginResponse } from "../types/auth.types";

export async function login(credentials: LoginCredentials): Promise<LoginResponse> {
  const csrfToken = await getCsrfToken();
  const response = await authClient.post<LoginResponse>("/auth/login/", credentials, {
    headers: { "X-CSRFToken": csrfToken },
  });
  return response.data;
}

/** Revokes the refresh token and clears its cookie. Works even when the access token has expired. */
export async function logout(): Promise<void> {
  const csrfToken = await getCsrfToken();
  await authClient.post("/auth/logout/", undefined, { headers: { "X-CSRFToken": csrfToken } });
}

export async function getCurrentUser(): Promise<CurrentUser> {
  const response = await apiClient.get<CurrentUser>("/auth/me/");
  return response.data;
}

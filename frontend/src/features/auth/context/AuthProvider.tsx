import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  getCsrfToken,
  refreshAccessToken,
  setAccessToken,
  setAuthenticationFailureHandler,
} from "../../../shared/api/authSession";
import * as authApi from "../api/authApi";
import type { CurrentUser, LoginCredentials } from "../types/auth.types";
import { AuthContext, type AuthContextValue } from "./authContext";

type AuthProviderProps = {
  children: ReactNode;
};

/**
 * Owns the signed-in session: the current user and the login/logout actions.
 * The access token itself lives in memory in `authSession`; this provider only
 * decides when it is set or cleared.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isRestoringSession, setIsRestoringSession] = useState(true);

  // Forget the session and every account-specific cache entry (README-frontend-architecture §4).
  // Safe to call repeatedly, e.g. when several in-flight requests fail at once.
  const endSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setIsRestoringSession(false);
    void queryClient.cancelQueries();
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    setAuthenticationFailureHandler(endSession);
    return () => setAuthenticationFailureHandler(() => {});
  }, [endSession]);

  // On page load the access token is gone, so ask the refresh cookie for a new one.
  // The refresh is the shared single-flight request, so React StrictMode's double
  // effect run in development cannot start two competing refreshes.
  useEffect(() => {
    let isCancelled = false;

    async function restoreSession() {
      try {
        await getCsrfToken();
        await refreshAccessToken();
        const restoredUser = await authApi.getCurrentUser();
        if (!isCancelled) {
          setUser(restoredUser);
        }
      } catch {
        // No valid refresh cookie: the visitor simply needs to sign in.
      } finally {
        if (!isCancelled) {
          setIsRestoringSession(false);
        }
      }
    }

    void restoreSession();
    return () => {
      isCancelled = true;
    };
  }, []);

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      const { access } = await authApi.login(credentials);
      setAccessToken(access);
      // Nothing cached for a previous account may be shown to this one.
      queryClient.clear();
      try {
        setUser(await authApi.getCurrentUser());
      } catch (error) {
        setAccessToken(null);
        throw error;
      }
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Revoking the refresh token failed (e.g. offline). The user still asked to sign out,
      // so this browser forgets the session regardless; the cookie expires on its own.
    }
    endSession();
  }, [endSession]);

  const contextValue = useMemo<AuthContextValue>(() => {
    const status = isRestoringSession ? "loading" : user ? "authenticated" : "unauthenticated";
    return { status, user, login, logout };
  }, [isRestoringSession, user, login, logout]);

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
}

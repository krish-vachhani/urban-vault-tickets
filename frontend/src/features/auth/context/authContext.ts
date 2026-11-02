import { createContext } from "react";

import type { CurrentUser, LoginCredentials } from "../types/auth.types";

/** `loading` lasts only while the app tries to restore a session after a page load. */
export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export type AuthContextValue = {
  status: AuthStatus;
  /** Set exactly when `status` is `authenticated`. */
  user: CurrentUser | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

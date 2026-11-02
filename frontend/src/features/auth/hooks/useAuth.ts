import { useContext } from "react";

import { AuthContext, type AuthContextValue } from "../context/authContext";

export function useAuth(): AuthContextValue {
  const authContext = useContext(AuthContext);
  if (!authContext) {
    throw new Error("useAuth must be used inside <AuthProvider>.");
  }
  return authContext;
}

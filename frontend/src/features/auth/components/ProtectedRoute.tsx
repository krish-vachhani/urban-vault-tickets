import { Navigate, Outlet, useLocation } from "react-router";

import { LoadingIndicator } from "../../../shared/components/LoadingIndicator";
import { useAuth } from "../hooks/useAuth";

/** Renders the nested routes only for a signed-in user; everyone else is sent to the login screen. */
export function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <LoadingIndicator label="Restoring your session" />;
  }
  if (status === "unauthenticated") {
    // Remember where the visitor was headed so login can send them back there.
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <Outlet />;
}

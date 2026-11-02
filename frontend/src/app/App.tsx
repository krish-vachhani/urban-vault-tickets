import { BrowserRouter } from "react-router";

import { AuthProvider } from "../features/auth/context/AuthProvider";
import { AppRoutes } from "./AppRoutes";
import { AppProviders } from "./providers/AppProviders";
import { createAppQueryClient } from "./providers/queryClient";

// Created once, outside any component, so re-renders never discard the cache.
const queryClient = createAppQueryClient();

export function App() {
  return (
    <AppProviders queryClient={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </AppProviders>
  );
}

import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";

import { AppProviders } from "../app/providers/AppProviders";
import { createAppQueryClient } from "../app/providers/queryClient";
import { AuthContext } from "../features/auth/context/authContext";
import type { CurrentUser } from "../features/auth/types/auth.types";

type RenderOptions = {
  initialPath?: string;
  /** Router state for the first location, e.g. a message left by the previous screen. */
  initialState?: unknown;
  /** The signed-in user; null renders as signed out. */
  user?: CurrentUser | null;
};

/** Renders UI inside the app's providers with a fresh QueryClient, a memory router, and a fixed signed-in user. */
export function renderWithProviders(ui: ReactElement, { initialPath = "/", initialState, user = null }: RenderOptions = {}) {
  // A fresh client per test keeps cached data from leaking between tests; no retries keeps failures immediate.
  const queryClient = createAppQueryClient();
  queryClient.setDefaultOptions({ queries: { retry: false } });

  const { pathname, search } = new URL(initialPath, "http://localhost");

  const authValue = {
    status: user ? ("authenticated" as const) : ("unauthenticated" as const),
    user,
    login: async () => {},
    logout: async () => {},
  };

  const renderResult = render(
    <AppProviders queryClient={queryClient}>
      <AuthContext.Provider value={authValue}>
        <MemoryRouter initialEntries={[{ pathname, search, state: initialState }]}>{ui}</MemoryRouter>
      </AuthContext.Provider>
    </AppProviders>,
  );
  return { ...renderResult, queryClient };
}

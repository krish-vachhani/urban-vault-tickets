import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as authApi from "../features/auth/api/authApi";
import { AuthProvider } from "../features/auth/context/AuthProvider";
import * as authSession from "../shared/api/authSession";
import * as healthApi from "../shared/api/healthApi";
import { buildCurrentUser } from "../test/factories";
import * as ticketsApi from "../features/tickets/api/ticketsApi";
import { AppRoutes } from "./AppRoutes";
import { AppProviders } from "./providers/AppProviders";
import { createAppQueryClient } from "./providers/queryClient";

function renderAppAt(path: string) {
  const queryClient = createAppQueryClient();
  queryClient.setDefaultOptions({ queries: { retry: false } });
  render(
    <AppProviders queryClient={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </MemoryRouter>
    </AppProviders>,
  );
}

describe("application routing and session", () => {
  beforeEach(() => {
    vi.spyOn(authSession, "getCsrfToken").mockResolvedValue("csrf");
    vi.spyOn(healthApi, "getApiHealth").mockResolvedValue({ status: "ok", database: "ok" });
  });

  it("sends a signed-out visitor from a protected page to the login screen", async () => {
    vi.spyOn(authSession, "refreshAccessToken").mockRejectedValue(new Error("401"));

    renderAppAt("/tickets");

    expect(await screen.findByRole("heading", { name: "Sign in to Urban Vault Tickets" })).toBeInTheDocument();
  });

  it("restores the session on a protected page and shows who is signed in", async () => {
    vi.spyOn(authSession, "refreshAccessToken").mockResolvedValue("token");
    vi.spyOn(authApi, "getCurrentUser").mockResolvedValue(buildCurrentUser());
    vi.spyOn(ticketsApi, "getTickets").mockResolvedValue({ count: 0, next: null, previous: null, results: [] });

    renderAppAt("/tickets");

    expect(await screen.findByText("Chaitanya M (Client POC)")).toBeInTheDocument();
    expect(await screen.findByText("There are no open tickets to show.")).toBeInTheDocument();
  });

  it("redirects the root path to the ticket list", async () => {
    vi.spyOn(authSession, "refreshAccessToken").mockResolvedValue("token");
    vi.spyOn(authApi, "getCurrentUser").mockResolvedValue(buildCurrentUser());
    vi.spyOn(ticketsApi, "getTickets").mockResolvedValue({ count: 0, next: null, previous: null, results: [] });

    renderAppAt("/");

    expect(await screen.findByRole("heading", { name: "Tickets" })).toBeInTheDocument();
  });

  it("shows a not-found page for unknown routes", async () => {
    vi.spyOn(authSession, "refreshAccessToken").mockRejectedValue(new Error("401"));

    renderAppAt("/does-not-exist");

    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});

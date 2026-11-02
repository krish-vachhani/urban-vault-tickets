import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as authSession from "../../../shared/api/authSession";
import { buildCurrentUser } from "../../../test/factories";
import * as authApi from "../api/authApi";
import { useAuth } from "../hooks/useAuth";
import { AuthProvider } from "./AuthProvider";

function AuthStatusProbe() {
  const { status, user, login, logout } = useAuth();
  return (
    <div>
      <p>Status: {status}</p>
      <p>User: {user?.name ?? "nobody"}</p>
      <button onClick={() => void login({ email: "chaitanya.m@urbanvault.test", password: "not-a-real-password" })}>
        Sign in
      </button>
      <button onClick={() => void logout()}>Sign out</button>
    </div>
  );
}

function renderAuthProvider(queryClient: QueryClient) {
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AuthStatusProbe />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("AuthProvider", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient();
    vi.spyOn(authSession, "getCsrfToken").mockResolvedValue("csrf");
  });

  afterEach(() => {
    authSession.setAccessToken(null);
    authSession.setAuthenticationFailureHandler(() => {});
  });

  it("restores the session on load from the refresh cookie", async () => {
    vi.spyOn(authSession, "refreshAccessToken").mockResolvedValue("new-access-token");
    vi.spyOn(authApi, "getCurrentUser").mockResolvedValue(buildCurrentUser({ name: "Chaitanya M" }));

    renderAuthProvider(queryClient);

    expect(screen.getByText("Status: loading")).toBeInTheDocument();
    expect(await screen.findByText("Status: authenticated")).toBeInTheDocument();
    expect(screen.getByText("User: Chaitanya M")).toBeInTheDocument();
  });

  it("is signed out when there is no valid refresh cookie", async () => {
    vi.spyOn(authSession, "refreshAccessToken").mockRejectedValue(new Error("401"));

    renderAuthProvider(queryClient);

    expect(await screen.findByText("Status: unauthenticated")).toBeInTheDocument();
  });

  it("clears the cached data and the access token on logout", async () => {
    vi.spyOn(authSession, "refreshAccessToken").mockResolvedValue("new-access-token");
    vi.spyOn(authApi, "getCurrentUser").mockResolvedValue(buildCurrentUser());
    const logoutSpy = vi.spyOn(authApi, "logout").mockResolvedValue();
    renderAuthProvider(queryClient);
    await screen.findByText("Status: authenticated");
    authSession.setAccessToken("in-memory-token");
    queryClient.setQueryData(["tickets", "list"], { results: ["private ticket"] });

    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByText("Status: unauthenticated")).toBeInTheDocument();
    expect(logoutSpy).toHaveBeenCalledOnce();
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
    expect(authSession.getAccessToken()).toBeNull();
  });

  it("still ends the local session when revoking the refresh token fails", async () => {
    vi.spyOn(authSession, "refreshAccessToken").mockResolvedValue("new-access-token");
    vi.spyOn(authApi, "getCurrentUser").mockResolvedValue(buildCurrentUser());
    vi.spyOn(authApi, "logout").mockRejectedValue(new Error("Network Error"));
    renderAuthProvider(queryClient);
    await screen.findByText("Status: authenticated");

    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByText("Status: unauthenticated")).toBeInTheDocument();
  });

  it("drops the previous account's cache when a new account signs in", async () => {
    vi.spyOn(authSession, "refreshAccessToken").mockRejectedValue(new Error("401"));
    vi.spyOn(authApi, "login").mockResolvedValue({ access: "access-for-new-account" });
    vi.spyOn(authApi, "getCurrentUser").mockResolvedValue(buildCurrentUser({ name: "Neha K" }));
    renderAuthProvider(queryClient);
    await screen.findByText("Status: unauthenticated");
    queryClient.setQueryData(["tickets", "list"], { results: ["previous account's ticket"] });

    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("User: Neha K")).toBeInTheDocument();
    expect(queryClient.getQueryData(["tickets", "list"])).toBeUndefined();
    expect(authSession.getAccessToken()).toBe("access-for-new-account");
  });

  it("ends the session and clears the cache when the API layer reports a terminal auth failure", async () => {
    vi.spyOn(authSession, "refreshAccessToken").mockResolvedValue("new-access-token");
    vi.spyOn(authApi, "getCurrentUser").mockResolvedValue(buildCurrentUser());
    renderAuthProvider(queryClient);
    await screen.findByText("Status: authenticated");
    queryClient.setQueryData(["tickets", "list"], { results: [] });

    authSession.notifyAuthenticationFailure();

    await waitFor(() => expect(screen.getByText("Status: unauthenticated")).toBeInTheDocument());
    expect(queryClient.getQueryData(["tickets", "list"])).toBeUndefined();
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError } from "axios";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as healthApi from "../../../shared/api/healthApi";
import { AppProviders } from "../../../app/providers/AppProviders";
import { createAppQueryClient } from "../../../app/providers/queryClient";
import { AuthContext, type AuthContextValue } from "../context/authContext";
import { DemoAccountPicker } from "../components/DemoAccountPicker";
import { LoginPage } from "./LoginPage";

function renderLoginPage(authOverrides: Partial<AuthContextValue> = {}) {
  const authValue: AuthContextValue = {
    status: "unauthenticated",
    user: null,
    login: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
    ...authOverrides,
  };
  render(
    <AppProviders queryClient={createAppQueryClient()}>
      <AuthContext.Provider value={authValue}>
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/tickets" element={<p>Ticket list screen</p>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </AppProviders>,
  );
  return authValue;
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.spyOn(healthApi, "getApiHealth").mockResolvedValue({ status: "ok", database: "ok" });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("asks for an email and password before calling login", async () => {
    const authValue = renderLoginPage();

    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(authValue.login).not.toHaveBeenCalled();
  });

  it("signs in with the entered credentials and opens the ticket list", async () => {
    const authValue = renderLoginPage();

    await userEvent.type(screen.getByLabelText("Email"), "chaitanya.m@urbanvault.test");
    await userEvent.type(screen.getByLabelText("Password"), "typed-by-the-user");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Ticket list screen")).toBeInTheDocument();
    expect(authValue.login).toHaveBeenCalledWith({
      email: "chaitanya.m@urbanvault.test",
      password: "typed-by-the-user",
    });
  });

  it("shows the API's message when the credentials are rejected", async () => {
    const rejection = new AxiosError("Request failed", "401", undefined, null, {
      status: 401,
      statusText: "",
      headers: {},
      config: {} as never,
      data: { error: { code: "NOT_AUTHENTICATED", message: "Invalid email or password.", details: {} } },
    });
    renderLoginPage({ login: vi.fn().mockRejectedValue(rejection) });

    await userEvent.type(screen.getByLabelText("Email"), "chaitanya.m@urbanvault.test");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
  });

  it("sends an already signed-in visitor straight to the ticket list", async () => {
    renderLoginPage({ status: "authenticated" });

    expect(await screen.findByText("Ticket list screen")).toBeInTheDocument();
  });

  it("hides the demo account picker when the development flag is off", () => {
    vi.stubEnv("VITE_ENABLE_DEMO_ACCOUNTS", "false");
    renderLoginPage();

    expect(screen.queryByText(/Demo account/)).not.toBeInTheDocument();
  });

  it("shows the demo account picker when the development flag is on", () => {
    vi.stubEnv("VITE_ENABLE_DEMO_ACCOUNTS", "true");
    renderLoginPage();

    expect(screen.getByRole("combobox", { name: /Demo account/ })).toBeInTheDocument();
  });
});

describe("DemoAccountPicker", () => {
  it("passes the chosen account's email to the form without signing in", async () => {
    const onSelectEmail = vi.fn();
    render(
      <AppProviders queryClient={createAppQueryClient()}>
        <DemoAccountPicker onSelectEmail={onSelectEmail} />
      </AppProviders>,
    );

    await userEvent.click(screen.getByRole("combobox", { name: /Demo account/ }));
    await userEvent.click(await screen.findByRole("option", { name: /Dhananjaya Murthy/ }));

    expect(onSelectEmail).toHaveBeenCalledWith("dhananjaya.m@urbanvault.test");
  });
});

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import * as healthApi from "../shared/api/healthApi";
import { AppRoutes } from "./AppRoutes";
import { AppProviders } from "./providers/AppProviders";
import { createAppQueryClient } from "./providers/queryClient";

function renderAppAt(path: string) {
  // A fresh QueryClient per test keeps cached data from leaking between tests.
  const queryClient = createAppQueryClient();
  queryClient.setDefaultOptions({ queries: { retry: false } });

  return render(
    <AppProviders queryClient={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
}

describe("application scaffold", () => {
  it("shows that the API is connected when the health check succeeds", async () => {
    vi.spyOn(healthApi, "getApiHealth").mockResolvedValue({ status: "ok", database: "ok" });

    renderAppAt("/");

    expect(screen.getByRole("heading", { name: "Urban Vault Tickets" })).toBeInTheDocument();
    expect(await screen.findByText("API connected")).toBeInTheDocument();
  });

  it("shows that the API is unavailable when the health check fails", async () => {
    vi.spyOn(healthApi, "getApiHealth").mockRejectedValue(new Error("Network Error"));

    renderAppAt("/");

    expect(await screen.findByText("API unavailable")).toBeInTheDocument();
  });

  it("shows a not-found page for unknown routes", () => {
    vi.spyOn(healthApi, "getApiHealth").mockResolvedValue({ status: "ok", database: "ok" });

    renderAppAt("/does-not-exist");

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});

import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { buildCurrentUser } from "../../../test/factories";
import { renderWithProviders } from "../../../test/renderWithProviders";
import * as referenceDataApi from "../../reference-data/api/referenceDataApi";
import { CreateTicketPage } from "./CreateTicketPage";

function renderCreatePage(role: "CLIENT" | "WORKER") {
  return renderWithProviders(
    <Routes>
      <Route path="/tickets/new" element={<CreateTicketPage />} />
    </Routes>,
    { initialPath: "/tickets/new", user: buildCurrentUser({ role }) },
  );
}

describe("CreateTicketPage", () => {
  it("shows the creation form to users who can create tickets", async () => {
    vi.spyOn(referenceDataApi, "getMyClients").mockResolvedValue([{ id: 1, name: "Harness" }]);
    vi.spyOn(referenceDataApi, "getClientOffices").mockResolvedValue([]);

    renderCreatePage("CLIENT");

    expect(screen.getByRole("heading", { name: "Create New Ticket" })).toBeInTheDocument();
    expect(await screen.findByText("Client: Harness")).toBeInTheDocument();
  });

  it("tells a Worker they cannot create tickets, without loading any form data", () => {
    const getMyClients = vi.spyOn(referenceDataApi, "getMyClients");

    renderCreatePage("WORKER");

    expect(screen.getByText("You do not have permission to create tickets.")).toBeInTheDocument();
    expect(getMyClients).not.toHaveBeenCalled();
  });
});

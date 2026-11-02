import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { buildCurrentUser, buildTicketSummary, technician } from "../../../test/factories";
import { renderWithProviders } from "../../../test/renderWithProviders";
import * as ticketsApi from "../api/ticketsApi";
import type { TicketFilterOptions } from "../types/ticket.types";
import { TicketListPage } from "./TicketListPage";

const FILTER_OPTIONS: TicketFilterOptions = {
  clients: [{ id: 1, name: "Harness" }],
  departments: [
    { id: 1, name: "Technical" },
    { id: 2, name: "IT" },
  ],
  facility_managers: [{ id: 4, name: "Chandan S" }],
  workflow_stages: [
    { value: "PENDING_TECHNICIAN_ASSIGNMENT", label: "Pending Technician Assignment" },
    { value: "PENDING_TECHNICIAN_ASSESSMENT", label: "Pending Technician Assessment" },
    { value: "PENDING_DEPARTMENT_POC_REVIEW", label: "Pending Department POC Review" },
  ],
};

function pageOf(count: number, ticketCount = 10) {
  return {
    count,
    next: null,
    previous: null,
    results: Array.from({ length: ticketCount }, (_unused, index) =>
      buildTicketSummary({ id: 100 + index, ticket_number: `TKT-${100 + index}` }),
    ),
  };
}

function CurrentUrl() {
  const location = useLocation();
  return <output aria-label="Current URL">{location.search}</output>;
}

function renderListAt(path: string, role: "CLIENT" | "WORKER" = "CLIENT") {
  return renderWithProviders(
    <Routes>
      <Route
        path="/tickets"
        element={
          <>
            <TicketListPage />
            <CurrentUrl />
          </>
        }
      />
    </Routes>,
    { initialPath: path, user: buildCurrentUser({ role }) },
  );
}

describe("TicketListPage", () => {
  beforeEach(() => {
    vi.spyOn(ticketsApi, "getTicketFilterOptions").mockResolvedValue(FILTER_OPTIONS);
  });

  it("shows ticket cards from the first page of the Open tab", async () => {
    const getTickets = vi.spyOn(ticketsApi, "getTickets").mockResolvedValue(pageOf(23));

    renderListAt("/tickets");

    expect(await screen.findByText("Showing 1–10 of 23 tickets")).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(10);
    expect(getTickets).toHaveBeenCalledWith(
      expect.objectContaining({ tab: "open", page: 1, pageSize: 10, ordering: "-created_at" }),
      expect.anything(),
    );
  });

  it("shows the card details from the wireframe", async () => {
    vi.spyOn(ticketsApi, "getTickets").mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        buildTicketSummary({
          floors: [],
          action_required: true,
          current_assignees: [buildTicketSummary().current_assignees[0]!, technician],
        }),
      ],
    });

    renderListAt("/tickets");

    const card = await screen.findByRole("article");
    expect(within(card).getByText("AC not cooling")).toBeInTheDocument();
    expect(within(card).getByText("Harness-1317; All Floors")).toBeInTheDocument();
    expect(within(card).getByText("#TKT-42")).toBeInTheDocument();
    expect(within(card).getByText("Pending Technician Assignment")).toBeInTheDocument();
    expect(within(card).getByText("Action Required")).toBeInTheDocument();
    expect(within(card).getByText(/Dhananjaya Murthy \(Technical Manager\) › Prakash Kumar \(Technician\)/)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "View TKT-42" })).toHaveAttribute("href", "/tickets/42");
  });

  it("requests the page from the URL and moves to the next page through the URL", async () => {
    const getTickets = vi.spyOn(ticketsApi, "getTickets").mockResolvedValue(pageOf(23));

    renderListAt("/tickets?page=2&tab=closed");
    await screen.findByText("Showing 11–20 of 23 tickets");
    expect(getTickets).toHaveBeenCalledWith(expect.objectContaining({ tab: "closed", page: 2 }), expect.anything());

    await userEvent.click(screen.getByRole("button", { name: "Go to page 3" }));

    expect(screen.getByLabelText("Current URL")).toHaveTextContent("?tab=closed&page=3");
    await waitFor(() =>
      expect(getTickets).toHaveBeenLastCalledWith(expect.objectContaining({ tab: "closed", page: 3 }), expect.anything()),
    );
  });

  it("switches tabs, starting again from page 1", async () => {
    const getTickets = vi.spyOn(ticketsApi, "getTickets").mockResolvedValue(pageOf(23));
    renderListAt("/tickets?page=3");
    await screen.findByText("Showing 21–30 of 23 tickets");

    await userEvent.click(screen.getByRole("tab", { name: "Closed Tickets" }));

    expect(screen.getByLabelText("Current URL")).toHaveTextContent("?tab=closed");
    await waitFor(() =>
      expect(getTickets).toHaveBeenLastCalledWith(expect.objectContaining({ tab: "closed", page: 1 }), expect.anything()),
    );
  });

  it("sorts oldest first through the Sort menu", async () => {
    const getTickets = vi.spyOn(ticketsApi, "getTickets").mockResolvedValue(pageOf(5, 5));
    renderListAt("/tickets");
    await screen.findByText("Showing 1–5 of 5 tickets");

    await userEvent.click(screen.getByRole("button", { name: "Sort" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Older First" }));

    expect(screen.getByLabelText("Current URL")).toHaveTextContent("?ordering=created_at");
    await waitFor(() =>
      expect(getTickets).toHaveBeenLastCalledWith(expect.objectContaining({ ordering: "created_at" }), expect.anything()),
    );
  });

  it("applies filters from the Filters dialog and resets to page 1", async () => {
    const getTickets = vi.spyOn(ticketsApi, "getTickets").mockResolvedValue(pageOf(23));
    renderListAt("/tickets?page=2");
    await screen.findByText("Showing 11–20 of 23 tickets");

    await userEvent.click(screen.getByRole("button", { name: "Filters" }));
    await userEvent.click(await screen.findByRole("combobox", { name: "Department" }));
    await userEvent.click(await screen.findByRole("option", { name: "IT" }));
    await userEvent.click(screen.getByRole("combobox", { name: "Ticket status" }));
    await userEvent.click(await screen.findByRole("option", { name: "Pending Technician Assessment" }));
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));

    expect(screen.getByLabelText("Current URL")).toHaveTextContent(
      "?department_id=2&workflow_stage=PENDING_TECHNICIAN_ASSESSMENT",
    );
    await waitFor(() =>
      expect(getTickets).toHaveBeenLastCalledWith(
        expect.objectContaining({ departmentId: 2, workflowStage: "PENDING_TECHNICIAN_ASSESSMENT", page: 1 }),
        expect.anything(),
      ),
    );
  });

  it("clears every filter with Clear all, even ones that are already in the URL", async () => {
    const getTickets = vi.spyOn(ticketsApi, "getTickets").mockResolvedValue(pageOf(3, 3));
    renderListAt("/tickets?department_id=2&workflow_stage=PENDING_TECHNICIAN_ASSESSMENT&tab=closed");
    await screen.findByText("Showing 1–3 of 3 tickets");

    await userEvent.click(screen.getByRole("button", { name: "Filters" }));
    await userEvent.click(await screen.findByRole("button", { name: "Clear all" }));
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));

    // The tab is not a filter, so it stays.
    expect(screen.getByLabelText("Current URL")).toHaveTextContent(/^\?tab=closed$/);
    await waitFor(() =>
      expect(getTickets).toHaveBeenLastCalledWith(
        expect.objectContaining({ departmentId: undefined, workflowStage: undefined, tab: "closed" }),
        expect.anything(),
      ),
    );
  });

  it("keeps a tab change made while a search is still waiting to be applied", async () => {
    vi.spyOn(ticketsApi, "getTickets").mockResolvedValue(pageOf(3, 3));
    renderListAt("/tickets");
    await screen.findByText("Showing 1–3 of 3 tickets");

    await userEvent.type(screen.getByRole("searchbox", { name: "Search issues" }), "lift");
    await userEvent.click(screen.getByRole("tab", { name: "Closed Tickets" }));

    await waitFor(() => expect(screen.getByLabelText("Current URL")).toHaveTextContent("?tab=closed&search=lift"));
  });

  it("searches Issue text after typing stops", async () => {
    const getTickets = vi.spyOn(ticketsApi, "getTickets").mockResolvedValue(pageOf(3, 3));
    renderListAt("/tickets");
    await screen.findByText("Showing 1–3 of 3 tickets");

    await userEvent.type(screen.getByRole("searchbox", { name: "Search issues" }), "lift");

    await waitFor(() => expect(screen.getByLabelText("Current URL")).toHaveTextContent("?search=lift"));
    expect(getTickets).toHaveBeenLastCalledWith(expect.objectContaining({ search: "lift", page: 1 }), expect.anything());
  });

  it("explains an empty result and lets the user clear the search", async () => {
    vi.spyOn(ticketsApi, "getTickets").mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    renderListAt("/tickets?search=zzz");

    expect(await screen.findByText("No tickets match your search or filters.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear search and filters" }));

    expect(screen.getByLabelText("Current URL")).toHaveTextContent("");
  });

  it("offers a way back when the page number is beyond the last page", async () => {
    vi.spyOn(ticketsApi, "getTickets").mockRejectedValue(
      Object.assign(new Error("Request failed"), {
        isAxiosError: true,
        response: {
          status: 400,
          data: { error: { code: "VALIDATION_ERROR", message: "Invalid page.", details: { page: ["Invalid page."] } } },
        },
      }),
    );
    renderListAt("/tickets?page=9");

    expect(await screen.findByText("That page does not exist. The list may have changed.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Go to first page" }));

    expect(screen.getByLabelText("Current URL")).toHaveTextContent("");
  });

  it("shows an error with a retry for unexpected failures", async () => {
    const getTickets = vi
      .spyOn(ticketsApi, "getTickets")
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue(pageOf(1, 1));
    renderListAt("/tickets");

    expect(await screen.findByText("Could not load tickets.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByRole("article")).toBeInTheDocument();
    expect(getTickets).toHaveBeenCalledTimes(2);
  });

  it("offers ticket creation to everyone except Workers", async () => {
    vi.spyOn(ticketsApi, "getTickets").mockResolvedValue(pageOf(1, 1));

    renderListAt("/tickets", "CLIENT");
    expect(await screen.findByRole("link", { name: "Create New Ticket" })).toHaveAttribute("href", "/tickets/new");
  });

  it("does not offer ticket creation to Workers", async () => {
    vi.spyOn(ticketsApi, "getTickets").mockResolvedValue(pageOf(1, 1));

    renderListAt("/tickets", "WORKER");
    await screen.findByRole("article");

    expect(screen.queryByRole("link", { name: "Create New Ticket" })).not.toBeInTheDocument();
  });
});

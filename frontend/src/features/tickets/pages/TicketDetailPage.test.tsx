import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError } from "axios";
import { Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { buildCurrentUser, buildTicketDetail, clientPoc, technicalManager, technician } from "../../../test/factories";
import { renderWithProviders } from "../../../test/renderWithProviders";
import * as ticketsApi from "../api/ticketsApi";
import type { ActivityItem } from "../types/ticket.types";
import { TicketDetailPage } from "./TicketDetailPage";

const ACTIVITY_FEED: ActivityItem[] = [
  {
    id: "action-1",
    type: "ACTION",
    event_type: "TICKET_CREATED",
    actor: clientPoc,
    description: "created the ticket.",
    change: null,
    note: null,
    created_at: "2025-10-27T06:10:00Z",
  },
  {
    id: "action-2",
    type: "ACTION",
    event_type: "WORKER_ASSIGNED",
    actor: technicalManager,
    description: "assigned technician.",
    change: { field: "assignee", from: "Unassigned", to: "Prakash Kumar (Technician)" },
    note: null,
    created_at: "2025-10-28T09:10:00Z",
  },
  {
    id: "action-3",
    type: "ACTION",
    event_type: "DEPARTMENT_CHANGED",
    actor: technicalManager,
    description: "changed department.",
    change: { field: "department", from: "Technical", to: "IT" },
    note: "Looks like an IT infrastructure problem.",
    created_at: "2025-10-28T10:10:00Z",
  },
  {
    id: "comment-1",
    type: "COMMENT",
    event_type: null,
    actor: technician,
    description: "Technician inspected the AC.",
    change: null,
    note: null,
    created_at: "2025-10-28T11:30:00Z",
  },
];

function renderDetail(initialState?: unknown) {
  return renderWithProviders(
    <Routes>
      <Route path="/tickets/:ticketId" element={<TicketDetailPage />} />
    </Routes>,
    { initialPath: "/tickets/42", initialState, user: buildCurrentUser() },
  );
}

function notFoundError(): AxiosError {
  return new AxiosError("Request failed", "404", undefined, null, {
    status: 404,
    statusText: "",
    headers: {},
    config: {} as never,
    data: { error: { code: "NOT_FOUND", message: "Not found.", details: {} } },
  });
}

function mockActivities(items: ActivityItem[] = ACTIVITY_FEED) {
  return vi.spyOn(ticketsApi, "getActivities").mockImplementation(async (_ticketId, type) => {
    const matching = items.filter((item) => type === "ALL" || (type === "ACTIONS") === (item.type === "ACTION"));
    return { count: matching.length, next: null, previous: null, results: matching };
  });
}

describe("TicketDetailPage", () => {
  beforeEach(() => {
    vi.spyOn(ticketsApi, "getTicket").mockResolvedValue(buildTicketDetail());
  });

  it("shows the ticket header and issue description", async () => {
    mockActivities();

    renderDetail();

    expect(await screen.findByRole("heading", { name: "AC not cooling" })).toBeInTheDocument();
    expect(screen.getByText("Harness-1317; 2F, 3F · #TKT-42")).toBeInTheDocument();
    expect(screen.getByText("The AC units on floors 2 and 3 are producing warm air.")).toBeInTheDocument();
    expect(screen.getByText("Status: Open")).toBeInTheDocument();
  });

  it("shows the success banner right after the ticket was created", async () => {
    mockActivities();

    renderDetail({ justCreated: true });

    expect(
      await screen.findByText("Ticket created successfully. If the issue is resolved, you can mark it as resolved."),
    ).toBeInTheDocument();
  });

  it("does not show the creation banner on an ordinary visit", async () => {
    mockActivities();

    renderDetail();
    await screen.findByRole("heading", { name: "AC not cooling" });

    expect(screen.queryByText(/Ticket created successfully/)).not.toBeInTheDocument();
  });

  it("lists Activity with the event count, History, forwarding note, and comments", async () => {
    mockActivities();

    renderDetail();

    expect(await screen.findByText("4 events")).toBeInTheDocument();
    expect(screen.getByText("Chaitanya M (Client POC)")).toBeInTheDocument();
    expect(screen.getByText("History: Unassigned → Prakash Kumar (Technician)")).toBeInTheDocument();
    expect(screen.getByText("History: Technical → IT")).toBeInTheDocument();
    expect(screen.getByText("Forwarding note: Looks like an IT infrastructure problem.")).toBeInTheDocument();
    expect(screen.getByText("Technician inspected the AC.")).toBeInTheDocument();
  });

  it("starts on All and asks the API for only comments when Comments is chosen", async () => {
    const getActivities = mockActivities();
    renderDetail();
    await screen.findByText("4 events");
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");

    await userEvent.click(screen.getByRole("button", { name: "Comments" }));

    expect(await screen.findByText("1 event")).toBeInTheDocument();
    expect(getActivities).toHaveBeenLastCalledWith(42, "COMMENTS", 1, 20, expect.anything());
    expect(screen.queryByText("History: Technical → IT")).not.toBeInTheDocument();
  });

  it("posts a comment and refreshes the feed", async () => {
    const getActivities = mockActivities();
    const addComment = vi.spyOn(ticketsApi, "addComment").mockResolvedValue({
      ...ACTIVITY_FEED[3]!,
      id: "comment-2",
      actor: clientPoc,
      description: "Thanks, please close this once fixed.",
    });
    renderDetail();
    await screen.findByText("4 events");
    const callsBeforePosting = getActivities.mock.calls.length;

    await userEvent.type(screen.getByLabelText("Write a comment"), "  Thanks, please close this once fixed.  ");
    await userEvent.click(screen.getByRole("button", { name: "Post" }));

    expect(addComment).toHaveBeenCalledWith(42, "Thanks, please close this once fixed.");
    await waitFor(() => expect(getActivities.mock.calls.length).toBeGreaterThan(callsBeforePosting));
    expect(screen.getByLabelText("Write a comment")).toHaveValue("");
  });

  it("does not post an empty comment", async () => {
    mockActivities();
    const addComment = vi.spyOn(ticketsApi, "addComment");
    renderDetail();
    await screen.findByText("4 events");

    await userEvent.type(screen.getByLabelText("Write a comment"), "   ");
    await userEvent.click(screen.getByRole("button", { name: "Post" }));

    expect(await screen.findByText("A comment is required.")).toBeInTheDocument();
    expect(addComment).not.toHaveBeenCalled();
  });

  it("shows the action panel the backend says this user may use", async () => {
    mockActivities();
    vi.spyOn(ticketsApi, "getTicket").mockResolvedValue(
      buildTicketDetail({
        available_actions: {
          can_assign_worker: false,
          can_change_department: false,
          can_submit_assessment: false,
          can_mark_resolved: true,
          can_comment: true,
        },
      }),
    );

    renderDetail();

    const actionPanel = await screen.findByRole("region", { name: "Ticket actions" });
    expect(within(actionPanel).getByRole("button", { name: "Mark Resolved" })).toBeInTheDocument();
  });

  it("replaces a cached ticket with the not-found message once the ticket leaves the user's view", async () => {
    mockActivities();
    vi.spyOn(ticketsApi, "getTicket")
      .mockResolvedValueOnce(buildTicketDetail())
      .mockRejectedValue(notFoundError());
    const { queryClient } = renderDetail();
    await screen.findByRole("heading", { name: "AC not cooling" });

    // e.g. the ticket was forwarded to another Department and a later refetch is refused.
    await queryClient.invalidateQueries({ queryKey: ["tickets"] });

    expect(await screen.findByRole("heading", { name: "Ticket not found" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Ticket actions" })).not.toBeInTheDocument();
  });

  it("explains a ticket that is missing or outside the user's access", async () => {
    vi.spyOn(ticketsApi, "getTicket").mockRejectedValue(notFoundError());

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Ticket not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to tickets" })).toHaveAttribute("href", "/tickets");
  });
});

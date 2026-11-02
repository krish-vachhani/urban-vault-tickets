import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError } from "axios";
import { Route, Routes, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { buildTicketDetail, technician } from "../../../test/factories";
import { renderWithProviders } from "../../../test/renderWithProviders";
import * as referenceDataApi from "../../reference-data/api/referenceDataApi";
import * as ticketsApi from "../api/ticketsApi";
import type { AvailableActions, TicketDetail } from "../types/ticket.types";
import { TicketActions } from "./TicketActions";

const NO_ACTIONS: AvailableActions = {
  can_assign_worker: false,
  can_change_department: false,
  can_submit_assessment: false,
  can_mark_resolved: false,
  can_comment: true,
};

function ticketWithActions(actions: Partial<AvailableActions>, overrides: Partial<TicketDetail> = {}): TicketDetail {
  return buildTicketDetail({ available_actions: { ...NO_ACTIONS, ...actions }, ...overrides });
}

/** Shows where the app navigated and any notice it passed along. */
function TicketListStub() {
  const location = useLocation();
  return <p>Ticket list. Notice: {(location.state as { notice?: string } | null)?.notice}</p>;
}

function renderActions(ticket: TicketDetail) {
  const onActionSucceeded = vi.fn();
  renderWithProviders(
    <Routes>
      <Route path="/tickets" element={<TicketListStub />} />
      <Route path="*" element={<TicketActions ticket={ticket} onActionSucceeded={onActionSucceeded} />} />
    </Routes>,
  );
  return { onActionSucceeded };
}

function buttonNames(): string[] {
  return screen.queryAllByRole("button").map((button) => button.textContent ?? "");
}

function apiError(status: number, code: string, message: string): AxiosError {
  return new AxiosError("Request failed", String(status), undefined, null, {
    status,
    statusText: "",
    headers: {},
    config: {} as never,
    data: { error: { code, message, details: {} } },
  });
}

describe("TicketActions: which actions each user is offered", () => {
  it("offers the Department POC Assign Worker and Change Department", () => {
    renderActions(ticketWithActions({ can_assign_worker: true, can_change_department: true }));

    expect(buttonNames()).toEqual(["Assign Worker", "Change Department"]);
    expect(screen.getByText("A new ticket has been assigned to you. Review it and take the next action.")).toBeInTheDocument();
  });

  it("offers the assigned Worker only Submit Assessment", () => {
    renderActions(ticketWithActions({ can_submit_assessment: true }, { workflow_stage: "PENDING_TECHNICIAN_ASSESSMENT" }));

    expect(buttonNames()).toEqual(["Submit Assessment"]);
    expect(screen.getByText("You have been assigned this ticket. Take action.")).toBeInTheDocument();
  });

  it("offers the Client (or the ticket's creator) only Mark Resolved", () => {
    renderActions(ticketWithActions({ can_mark_resolved: true }));

    expect(buttonNames()).toEqual(["Mark Resolved"]);
  });

  it("offers nothing to a Facility Manager viewing a ticket they did not create", () => {
    renderActions(ticketWithActions({}));

    expect(screen.queryByRole("region", { name: "Ticket actions" })).not.toBeInTheDocument();
    expect(buttonNames()).toEqual([]);
  });

  it("offers nothing to a previously assigned Worker, who can only view the ticket", () => {
    renderActions(
      ticketWithActions({}, { status: "CLOSED", workflow_stage: "PENDING_TECHNICIAN_ASSESSMENT", current_worker: null }),
    );

    expect(buttonNames()).toEqual([]);
  });
});

describe("TicketActions: submitting an action", () => {
  beforeEach(() => {
    vi.spyOn(ticketsApi, "getEligibleWorkers").mockResolvedValue([technician]);
    vi.spyOn(referenceDataApi, "getDepartments").mockResolvedValue([
      { id: 1, name: "Technical" },
      { id: 2, name: "IT" },
    ]);
  });

  it("assigns the chosen Worker", async () => {
    const assignWorker = vi.spyOn(ticketsApi, "assignWorker").mockResolvedValue({
      message: "Worker assigned successfully.",
      ticket_id: 42,
      workflow_stage: "PENDING_TECHNICIAN_ASSESSMENT",
      worker: technician,
    });
    const { onActionSucceeded } = renderActions(ticketWithActions({ can_assign_worker: true, can_change_department: true }));

    await userEvent.click(screen.getByRole("button", { name: "Assign Worker" }));
    await userEvent.click(await screen.findByRole("combobox", { name: "Select worker" }));
    await userEvent.click(await screen.findByRole("option", { name: "Prakash Kumar (Technician)" }));
    await userEvent.click(screen.getByRole("button", { name: "Ok" }));

    expect(assignWorker).toHaveBeenCalledWith(42, technician.id);
    expect(onActionSucceeded).toHaveBeenCalledWith("Worker assigned successfully.");
  });

  it("asks the POC to choose a Worker before calling the API", async () => {
    const assignWorker = vi.spyOn(ticketsApi, "assignWorker");
    renderActions(ticketWithActions({ can_assign_worker: true }));

    await userEvent.click(screen.getByRole("button", { name: "Assign Worker" }));
    await userEvent.click(await screen.findByRole("button", { name: "Ok" }));

    expect(await screen.findByText("Select a worker.")).toBeInTheDocument();
    expect(assignWorker).not.toHaveBeenCalled();
  });

  it("shows the API's conflict message when the ticket has already moved on", async () => {
    vi.spyOn(ticketsApi, "assignWorker").mockRejectedValue(
      apiError(409, "INVALID_TICKET_TRANSITION", "Ticket is not awaiting technician assignment."),
    );
    renderActions(ticketWithActions({ can_assign_worker: true }));

    await userEvent.click(screen.getByRole("button", { name: "Assign Worker" }));
    await userEvent.click(await screen.findByRole("combobox", { name: "Select worker" }));
    await userEvent.click(await screen.findByRole("option", { name: /Prakash Kumar/ }));
    await userEvent.click(screen.getByRole("button", { name: "Ok" }));

    expect(await screen.findByText("Ticket is not awaiting technician assignment.")).toBeInTheDocument();
  });

  it("requires a forwarding note, then forwards to another Department and leaves the ticket", async () => {
    const changeDepartment = vi.spyOn(ticketsApi, "changeDepartment").mockResolvedValue({
      ticket_id: 42,
      current_department: { id: 2, name: "IT" },
      workflow_stage: "PENDING_TECHNICIAN_ASSIGNMENT",
      status: "OPEN",
    });
    renderActions(ticketWithActions({ can_change_department: true }));

    await userEvent.click(screen.getByRole("button", { name: "Change Department" }));
    await userEvent.click(await screen.findByRole("combobox", { name: "Select department" }));
    // The ticket's current Department is not offered as a destination.
    expect(screen.queryByRole("option", { name: "Technical" })).not.toBeInTheDocument();
    await userEvent.click(await screen.findByRole("option", { name: "IT" }));
    await userEvent.click(screen.getByRole("button", { name: "Ok" }));

    expect(await screen.findByText("A forwarding note is required.")).toBeInTheDocument();
    expect(changeDepartment).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText(/Forwarding note/), "This looks like an IT infrastructure issue.");
    await userEvent.click(screen.getByRole("button", { name: "Ok" }));

    expect(changeDepartment).toHaveBeenCalledWith(42, 2, "This looks like an IT infrastructure issue.");
    expect(await screen.findByText(/Ticket list\. Notice: Ticket forwarded to the IT department\./)).toBeInTheDocument();
  });

  it("submits the chosen assessment outcome", async () => {
    const submitAssessment = vi.spyOn(ticketsApi, "submitAssessment").mockResolvedValue({
      ticket_id: 42,
      outcome: "PARTIALLY_RESOLVED",
      workflow_stage: "PENDING_DEPARTMENT_POC_REVIEW",
      status: "TECHNICIAN_CLOSED",
    });
    const { onActionSucceeded } = renderActions(ticketWithActions({ can_submit_assessment: true }));

    await userEvent.click(screen.getByRole("button", { name: "Submit Assessment" }));
    await userEvent.click(await screen.findByRole("button", { name: "Submit" }));
    expect(await screen.findByText("Choose one of the assessment options.")).toBeInTheDocument();
    expect(submitAssessment).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("radio", { name: /Mark Partially Resolved/ }));
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(submitAssessment).toHaveBeenCalledWith(42, "PARTIALLY_RESOLVED");
    expect(onActionSucceeded).toHaveBeenCalledOnce();
  });

  it("marks the ticket resolved after confirmation", async () => {
    const markResolved = vi.spyOn(ticketsApi, "markResolved").mockResolvedValue({
      ticket_id: 42,
      workflow_stage: "PENDING_TECHNICIAN_ASSIGNMENT",
      status: "CLOSED",
      closed_by: technician,
      closed_at: "2025-10-28T06:10:00Z",
    });
    const { onActionSucceeded } = renderActions(ticketWithActions({ can_mark_resolved: true }));

    await userEvent.click(screen.getByRole("button", { name: "Mark Resolved" }));
    expect(screen.getByText("If the issue no longer persists, you can mark it as resolved.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(markResolved).toHaveBeenCalledWith(42);
    expect(onActionSucceeded).toHaveBeenCalledWith("Ticket marked as resolved and moved to Closed Tickets.");
  });
});

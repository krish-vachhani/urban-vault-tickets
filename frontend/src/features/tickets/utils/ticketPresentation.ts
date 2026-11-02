import type { TicketSummary } from "../types/ticket.types";

const NO_FLOORS_LABEL = "All Floors";
const UNASSIGNED_LABEL = "Unassigned";

export function describeIssues(ticket: TicketSummary): string {
  return ticket.issues.map((issue) => issue.name).join(", ");
}

/** "Harness-1317; 2F, 3F", or "HSR-1317; All Floors" when the ticket has no Floor rows. */
export function describeLocation(ticket: TicketSummary): string {
  const floorNames = ticket.floors.length > 0 ? ticket.floors.map((floor) => floor.name).join(", ") : NO_FLOORS_LABEL;
  return `${ticket.client_office.name}; ${floorNames}`;
}

/** Assignees as a chain, e.g. "Dhananjaya Murthy (Technical Manager) › Unassigned". */
export function describeAssignees(ticket: TicketSummary): string {
  const assigneeLabels = ticket.current_assignees.map((person) => `${person.name} (${person.role_label})`);
  const hasWorker = ticket.current_assignees.some((person) => person.role === "WORKER");
  if (!hasWorker) {
    assigneeLabels.push(UNASSIGNED_LABEL);
  }
  return assigneeLabels.join(" › ");
}

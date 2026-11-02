import type { CurrentUser } from "../features/auth/types/auth.types";
import type { TicketDetail, TicketSummary } from "../features/tickets/types/ticket.types";
import type { UserSummary } from "../shared/types/api.types";

export const technicalManager: UserSummary = {
  id: 6,
  name: "Dhananjaya Murthy",
  role: "DEPARTMENT_POC",
  role_label: "Technical Manager",
};

export const technician: UserSummary = {
  id: 9,
  name: "Prakash Kumar",
  role: "WORKER",
  role_label: "Technician",
};

export const clientPoc: UserSummary = { id: 1, name: "Chaitanya M", role: "CLIENT", role_label: "Client POC" };

export function buildCurrentUser(overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    id: 1,
    name: "Chaitanya M",
    email: "chaitanya.m@urbanvault.test",
    role: "CLIENT",
    role_label: "Client POC",
    department: null,
    clients: [{ id: 1, name: "Harness" }],
    ...overrides,
  };
}

export function buildTicketSummary(overrides: Partial<TicketSummary> = {}): TicketSummary {
  return {
    id: 42,
    ticket_number: "TKT-42",
    client: { id: 1, name: "Harness" },
    client_office: { id: 1, name: "Harness-1317" },
    issues: [{ id: 101, name: "AC not cooling" }],
    floors: [
      { id: 2, name: "2F" },
      { id: 3, name: "3F" },
    ],
    workflow_stage: "PENDING_TECHNICIAN_ASSIGNMENT",
    status: "OPEN",
    created_by: clientPoc,
    created_at: "2025-10-27T06:10:00Z",
    current_department: { id: 1, name: "Technical" },
    current_assignees: [technicalManager],
    action_required: false,
    ...overrides,
  };
}

/** A ticket as seen by a user who has no actions available; tests switch on what they need. */
export function buildTicketDetail(overrides: Partial<TicketDetail> = {}): TicketDetail {
  return {
    ...buildTicketSummary(),
    description: "The AC units on floors 2 and 3 are producing warm air.",
    origin_department: { id: 1, name: "Technical" },
    closed_by: null,
    closed_at: null,
    current_poc: technicalManager,
    current_worker: null,
    assessment: null,
    available_actions: {
      can_assign_worker: false,
      can_change_department: false,
      can_submit_assessment: false,
      can_mark_resolved: false,
      can_comment: true,
    },
    ...overrides,
  };
}

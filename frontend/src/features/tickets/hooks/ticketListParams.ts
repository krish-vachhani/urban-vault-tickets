import type { TicketListParams, TicketOrdering, TicketTab, WorkflowStage } from "../types/ticket.types";

export const TICKET_LIST_PAGE_SIZE = 10;
export const DEFAULT_TICKET_TAB: TicketTab = "open";
export const DEFAULT_TICKET_ORDERING: TicketOrdering = "-created_at";

const WORKFLOW_STAGES: WorkflowStage[] = [
  "PENDING_TECHNICIAN_ASSIGNMENT",
  "PENDING_TECHNICIAN_ASSESSMENT",
  "PENDING_DEPARTMENT_POC_REVIEW",
];

function readPositiveInteger(value: string | null): number | undefined {
  if (value === null || !/^\d+$/.test(value)) {
    return undefined;
  }
  const parsed = Number(value);
  return parsed > 0 ? parsed : undefined;
}

/** Reads the list state from the URL. Missing or unusable values fall back to the defaults. */
export function parseTicketListParams(searchParams: URLSearchParams): TicketListParams {
  const workflowStage = WORKFLOW_STAGES.find((stage) => stage === searchParams.get("workflow_stage"));
  return {
    tab: searchParams.get("tab") === "closed" ? "closed" : DEFAULT_TICKET_TAB,
    page: readPositiveInteger(searchParams.get("page")) ?? 1,
    pageSize: TICKET_LIST_PAGE_SIZE,
    search: searchParams.get("search")?.trim() || undefined,
    clientId: readPositiveInteger(searchParams.get("client_id")),
    departmentId: readPositiveInteger(searchParams.get("department_id")),
    facilityManagerId: readPositiveInteger(searchParams.get("facility_manager_id")),
    workflowStage,
    ordering: searchParams.get("ordering") === "created_at" ? "created_at" : DEFAULT_TICKET_ORDERING,
  };
}

/** Writes the list state to URL parameters, leaving out defaults so shared links stay short. */
export function toSearchParams(params: TicketListParams): URLSearchParams {
  const searchParams = new URLSearchParams();
  if (params.tab !== DEFAULT_TICKET_TAB) searchParams.set("tab", params.tab);
  if (params.page > 1) searchParams.set("page", String(params.page));
  if (params.search) searchParams.set("search", params.search);
  if (params.clientId) searchParams.set("client_id", String(params.clientId));
  if (params.departmentId) searchParams.set("department_id", String(params.departmentId));
  if (params.facilityManagerId) searchParams.set("facility_manager_id", String(params.facilityManagerId));
  if (params.workflowStage) searchParams.set("workflow_stage", params.workflowStage);
  if (params.ordering !== DEFAULT_TICKET_ORDERING) searchParams.set("ordering", params.ordering);
  return searchParams;
}

export function countActiveFilters(params: TicketListParams): number {
  return [params.clientId, params.departmentId, params.facilityManagerId, params.workflowStage].filter(
    (filterValue) => filterValue !== undefined,
  ).length;
}

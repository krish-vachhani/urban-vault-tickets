import { apiClient } from "../../../shared/api/axiosClient";
import type { PaginatedResponse, ResultsResponse, UserSummary } from "../../../shared/types/api.types";
import type {
  ActivityFilter,
  ActivityItem,
  AssessmentOutcome,
  AssignWorkerResult,
  ChangeDepartmentResult,
  CreateTicketPayload,
  MarkResolvedResult,
  SubmitAssessmentResult,
  TicketDetail,
  TicketFilterOptions,
  TicketListParams,
  TicketSummary,
} from "../types/ticket.types";

/** Translates the list state into the API's query parameters, leaving out inactive filters. */
function toListQueryParams(params: TicketListParams) {
  return {
    tab: params.tab,
    page: params.page,
    page_size: params.pageSize,
    search: params.search || undefined,
    client_id: params.clientId,
    department_id: params.departmentId,
    facility_manager_id: params.facilityManagerId,
    workflow_stage: params.workflowStage,
    ordering: params.ordering,
  };
}

export async function getTickets(
  params: TicketListParams,
  signal?: AbortSignal,
): Promise<PaginatedResponse<TicketSummary>> {
  const response = await apiClient.get<PaginatedResponse<TicketSummary>>("/tickets/", {
    params: toListQueryParams(params),
    signal,
  });
  return response.data;
}

export async function getTicketFilterOptions(signal?: AbortSignal): Promise<TicketFilterOptions> {
  const response = await apiClient.get<TicketFilterOptions>("/tickets/filter-options/", { signal });
  return response.data;
}

export async function getTicket(ticketId: number, signal?: AbortSignal): Promise<TicketDetail> {
  const response = await apiClient.get<TicketDetail>(`/tickets/${ticketId}/`, { signal });
  return response.data;
}

export async function createTicket(payload: CreateTicketPayload): Promise<TicketDetail> {
  const response = await apiClient.post<TicketDetail>("/tickets/", payload);
  return response.data;
}

export async function getEligibleWorkers(ticketId: number, signal?: AbortSignal): Promise<UserSummary[]> {
  const response = await apiClient.get<ResultsResponse<UserSummary>>(`/tickets/${ticketId}/eligible-workers/`, {
    signal,
  });
  return response.data.results;
}

export async function assignWorker(ticketId: number, workerId: number): Promise<AssignWorkerResult> {
  const response = await apiClient.post<AssignWorkerResult>(`/tickets/${ticketId}/assign-worker/`, {
    worker_id: workerId,
  });
  return response.data;
}

export async function changeDepartment(
  ticketId: number,
  departmentId: number,
  forwardingNote: string,
): Promise<ChangeDepartmentResult> {
  const response = await apiClient.post<ChangeDepartmentResult>(`/tickets/${ticketId}/change-department/`, {
    department_id: departmentId,
    forwarding_note: forwardingNote,
  });
  return response.data;
}

export async function submitAssessment(
  ticketId: number,
  outcome: AssessmentOutcome,
): Promise<SubmitAssessmentResult> {
  const response = await apiClient.post<SubmitAssessmentResult>(`/tickets/${ticketId}/submit-assessment/`, {
    outcome,
  });
  return response.data;
}

export async function markResolved(ticketId: number): Promise<MarkResolvedResult> {
  const response = await apiClient.post<MarkResolvedResult>(`/tickets/${ticketId}/mark-resolved/`);
  return response.data;
}

export async function getActivities(
  ticketId: number,
  type: ActivityFilter,
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<PaginatedResponse<ActivityItem>> {
  const response = await apiClient.get<PaginatedResponse<ActivityItem>>(`/tickets/${ticketId}/activities/`, {
    params: { type, page, page_size: pageSize },
    signal,
  });
  return response.data;
}

export async function addComment(ticketId: number, body: string): Promise<ActivityItem> {
  const response = await apiClient.post<ActivityItem>(`/tickets/${ticketId}/comments/`, { body });
  return response.data;
}

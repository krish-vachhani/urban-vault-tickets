import { apiClient } from "../../../shared/api/axiosClient";
import type { ResultsResponse } from "../../../shared/types/api.types";
import type { IssueSearchParams } from "./referenceDataKeys";
import type {
  Client,
  ClientOffice,
  Department,
  Floor,
  Issue,
  QuickIssue,
} from "../types/referenceData.types";

export async function getMyClients(signal?: AbortSignal): Promise<Client[]> {
  const response = await apiClient.get<ResultsResponse<Client>>("/me/clients/", { signal });
  return response.data.results;
}

export async function getClientOffices(clientId: number, signal?: AbortSignal): Promise<ClientOffice[]> {
  const response = await apiClient.get<ResultsResponse<ClientOffice>>(`/clients/${clientId}/offices/`, { signal });
  return response.data.results;
}

export async function getOfficeFloors(clientOfficeId: number, signal?: AbortSignal): Promise<Floor[]> {
  const response = await apiClient.get<ResultsResponse<Floor>>(`/client-offices/${clientOfficeId}/floors/`, {
    signal,
  });
  return response.data.results;
}

export async function getDepartments(signal?: AbortSignal): Promise<Department[]> {
  const response = await apiClient.get<ResultsResponse<Department>>("/departments/", { signal });
  return response.data.results;
}

export async function searchIssues({ search, departmentId }: IssueSearchParams, signal?: AbortSignal): Promise<Issue[]> {
  const response = await apiClient.get<ResultsResponse<Issue>>("/issues/", {
    params: { search: search || undefined, department_id: departmentId ?? undefined },
    signal,
  });
  return response.data.results;
}

export async function getQuickIssues(clientId: number, signal?: AbortSignal): Promise<QuickIssue[]> {
  const response = await apiClient.get<ResultsResponse<QuickIssue>>(`/clients/${clientId}/quick-issues/`, { signal });
  return response.data.results;
}

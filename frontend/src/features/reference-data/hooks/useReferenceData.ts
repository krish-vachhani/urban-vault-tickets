import { keepPreviousData, useQuery } from "@tanstack/react-query";

import {
  getClientOffices,
  getDepartments,
  getMyClients,
  getOfficeFloors,
  getQuickIssues,
  searchIssues,
} from "../api/referenceDataApi";
import { referenceDataKeys, type IssueSearchParams } from "../api/referenceDataKeys";

/** Reference data changes rarely, so it can stay fresh much longer than ticket data. */
const REFERENCE_DATA_STALE_TIME_MS = 5 * 60 * 1000;

export function useMyClients() {
  return useQuery({
    queryKey: referenceDataKeys.myClients(),
    queryFn: ({ signal }) => getMyClients(signal),
    staleTime: REFERENCE_DATA_STALE_TIME_MS,
  });
}

/** Offices load only once a Client is chosen. */
export function useClientOffices(clientId: number | null) {
  return useQuery({
    queryKey: referenceDataKeys.clientOffices(clientId ?? 0),
    queryFn: ({ signal }) => getClientOffices(clientId ?? 0, signal),
    enabled: clientId !== null,
    staleTime: REFERENCE_DATA_STALE_TIME_MS,
  });
}

/** Floors load only once an Office is chosen. */
export function useOfficeFloors(clientOfficeId: number | null) {
  return useQuery({
    queryKey: referenceDataKeys.officeFloors(clientOfficeId ?? 0),
    queryFn: ({ signal }) => getOfficeFloors(clientOfficeId ?? 0, signal),
    enabled: clientOfficeId !== null,
    staleTime: REFERENCE_DATA_STALE_TIME_MS,
  });
}

export function useDepartments() {
  return useQuery({
    queryKey: referenceDataKeys.departments(),
    queryFn: ({ signal }) => getDepartments(signal),
    staleTime: REFERENCE_DATA_STALE_TIME_MS,
  });
}

/** Typing in the Issue picker changes the key, and the previous options stay visible until new ones arrive. */
export function useIssueSearch(params: IssueSearchParams) {
  return useQuery({
    queryKey: referenceDataKeys.issues(params),
    queryFn: ({ signal }) => searchIssues(params, signal),
    placeholderData: keepPreviousData,
    staleTime: REFERENCE_DATA_STALE_TIME_MS,
  });
}

/** Quick Issues depend on ticket history, so they use the default (short) staleness. */
export function useQuickIssues(clientId: number | null) {
  return useQuery({
    queryKey: referenceDataKeys.quickIssues(clientId ?? 0),
    queryFn: ({ signal }) => getQuickIssues(clientId ?? 0, signal),
    enabled: clientId !== null,
  });
}

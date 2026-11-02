import { useMutation, useQueryClient } from "@tanstack/react-query";

import { referenceDataKeys } from "../../reference-data/api/referenceDataKeys";
import {
  addComment,
  assignWorker,
  changeDepartment,
  createTicket,
  markResolved,
  submitAssessment,
} from "../api/ticketsApi";
import { ticketKeys } from "../api/ticketKeys";
import type { AssessmentOutcome, CreateTicketPayload } from "../types/ticket.types";

/*
 * Each mutation calls one explicit action endpoint and then marks the affected
 * queries stale so every mounted view refetches from the backend
 * (README-frontend-architecture §8). Nothing is updated optimistically, and
 * mutations are never retried (see queryClient.ts).
 *
 * Invalidating the whole "tickets" family covers the table in that section:
 * lists, filter options, details, Activity, and eligible Workers.
 */

type CreateTicketVariables = {
  /** Needed only to refresh that Client's Quick Issues; the API derives the Client from the Office. */
  clientId: number;
  payload: CreateTicketPayload;
};

export function useCreateTicket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ payload }: CreateTicketVariables) => createTicket(payload),
    onSuccess: (_createdTicket, { clientId }) => {
      void queryClient.invalidateQueries({ queryKey: ticketKeys.all });
      // A new ticket changes which Issues are most frequent for this Client.
      void queryClient.invalidateQueries({ queryKey: referenceDataKeys.quickIssues(clientId) });
    },
  });
}

/** After a failed action (e.g. 409: the ticket moved on), refetching also corrects what the screen offers. */
function useRefreshTicketDataWhenSettled() {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: ticketKeys.all });
}

export function useAssignWorker(ticketId: number) {
  const refreshTicketData = useRefreshTicketDataWhenSettled();
  return useMutation({
    mutationKey: ticketKeys.actions(ticketId),
    mutationFn: (workerId: number) => assignWorker(ticketId, workerId),
    onSettled: refreshTicketData,
  });
}

type ChangeDepartmentVariables = {
  departmentId: number;
  forwardingNote: string;
};

export function useChangeDepartment(ticketId: number) {
  const refreshTicketData = useRefreshTicketDataWhenSettled();
  return useMutation({
    mutationKey: ticketKeys.actions(ticketId),
    mutationFn: ({ departmentId, forwardingNote }: ChangeDepartmentVariables) =>
      changeDepartment(ticketId, departmentId, forwardingNote),
    onSettled: refreshTicketData,
  });
}

export function useSubmitAssessment(ticketId: number) {
  const refreshTicketData = useRefreshTicketDataWhenSettled();
  return useMutation({
    mutationKey: ticketKeys.actions(ticketId),
    mutationFn: (outcome: AssessmentOutcome) => submitAssessment(ticketId, outcome),
    onSettled: refreshTicketData,
  });
}

export function useMarkResolved(ticketId: number) {
  const refreshTicketData = useRefreshTicketDataWhenSettled();
  return useMutation({
    mutationKey: ticketKeys.actions(ticketId),
    mutationFn: () => markResolved(ticketId),
    onSettled: refreshTicketData,
  });
}

export function useAddComment(ticketId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => addComment(ticketId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...ticketKeys.all, ticketId, "activities"] });
    },
  });
}

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { getActivities } from "../api/ticketsApi";
import { ticketKeys } from "../api/ticketKeys";
import type { ActivityFilter } from "../types/ticket.types";

export const ACTIVITY_PAGE_SIZE = 20;

export function useTicketActivities(ticketId: number, filter: ActivityFilter, page: number) {
  return useQuery({
    queryKey: ticketKeys.activities(ticketId, filter, page),
    queryFn: ({ signal }) => getActivities(ticketId, filter, page, ACTIVITY_PAGE_SIZE, signal),
    placeholderData: keepPreviousData,
  });
}

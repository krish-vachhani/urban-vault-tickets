import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { getTicket, getTicketFilterOptions, getTickets } from "../api/ticketsApi";
import { ticketKeys } from "../api/ticketKeys";
import type { TicketListParams } from "../types/ticket.types";

/** One page of tickets. The previous page stays on screen (flagged as placeholder) while the next loads. */
export function useTicketList(params: TicketListParams) {
  return useQuery({
    queryKey: ticketKeys.list(params),
    queryFn: ({ signal }) => getTickets(params, signal),
    placeholderData: keepPreviousData,
  });
}

export function useTicketFilterOptions() {
  return useQuery({
    queryKey: ticketKeys.filterOptions(),
    queryFn: ({ signal }) => getTicketFilterOptions(signal),
  });
}

export function useTicket(ticketId: number) {
  return useQuery({
    queryKey: ticketKeys.detail(ticketId),
    queryFn: ({ signal }) => getTicket(ticketId, signal),
  });
}

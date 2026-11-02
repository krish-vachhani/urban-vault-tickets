import { useQuery } from "@tanstack/react-query";

import { getEligibleWorkers } from "../api/ticketsApi";
import { ticketKeys } from "../api/ticketKeys";

/** Only the Department POC of a ticket awaiting assignment may load this list; others get 403/409. */
export function useEligibleWorkers(ticketId: number) {
  return useQuery({
    queryKey: ticketKeys.eligibleWorkers(ticketId),
    queryFn: ({ signal }) => getEligibleWorkers(ticketId, signal),
  });
}

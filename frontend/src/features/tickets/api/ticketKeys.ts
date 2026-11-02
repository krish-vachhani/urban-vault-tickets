import type { ActivityFilter, TicketListParams } from "../types/ticket.types";

/** Query keys for ticket data (README-frontend-architecture §5). Every changing input is part of the key. */
export const ticketKeys = {
  all: ["tickets"] as const,
  lists: () => [...ticketKeys.all, "list"] as const,
  list: (params: TicketListParams) => [...ticketKeys.lists(), params] as const,
  filterOptions: () => [...ticketKeys.all, "filter-options"] as const,
  details: () => [...ticketKeys.all, "detail"] as const,
  detail: (ticketId: number) => [...ticketKeys.details(), ticketId] as const,
  activities: (ticketId: number, type: ActivityFilter, page: number) =>
    [...ticketKeys.all, ticketId, "activities", type, page] as const,
  eligibleWorkers: (ticketId: number) => [...ticketKeys.all, ticketId, "eligible-workers"] as const,
};

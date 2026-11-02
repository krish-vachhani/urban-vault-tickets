import type { UserRole } from "../../shared/types/api.types";

/**
 * Whether to offer the "Create New Ticket" button. This only decides what to
 * render; the API rejects a Worker's creation attempt with 403 regardless.
 */
export function shouldOfferTicketCreation(role: UserRole): boolean {
  return role !== "WORKER";
}

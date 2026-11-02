import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router";

import type { TicketListParams } from "../types/ticket.types";
import { parseTicketListParams, toSearchParams } from "./ticketListParams";

type UpdateOptions = {
  /** Replace the current history entry instead of adding one (used while typing a search). */
  replace?: boolean;
};

/**
 * The ticket list's tab, page, search, filters, and ordering, stored in the URL so
 * refresh, deep links, and the Back button all keep them (README-frontend-architecture §13).
 */
export function useTicketListParams() {
  const [searchParams, setSearchParams] = useSearchParams();
  const params = useMemo(() => parseTicketListParams(searchParams), [searchParams]);

  const updateParams = useCallback(
    (changes: Partial<TicketListParams>, options: UpdateOptions = {}) => {
      // Any change to what is listed starts again from page 1, unless it sets the page itself.
      const nextParams: TicketListParams = { ...params, page: 1, ...changes };
      setSearchParams(toSearchParams(nextParams), { replace: options.replace });
    },
    [params, setSearchParams],
  );

  return { params, updateParams };
}

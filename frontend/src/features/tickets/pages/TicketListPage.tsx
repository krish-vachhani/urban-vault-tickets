import FilterListIcon from "@mui/icons-material/FilterList";
import Alert from "@mui/material/Alert";
import Badge from "@mui/material/Badge";
import Button from "@mui/material/Button";
import LinearProgress from "@mui/material/LinearProgress";
import Pagination from "@mui/material/Pagination";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { Link as RouterLink, useLocation } from "react-router";

import { parseApiError } from "../../../shared/api/apiError";
import { ErrorMessage } from "../../../shared/components/ErrorMessage";
import { LoadingIndicator } from "../../../shared/components/LoadingIndicator";
import { shouldOfferTicketCreation } from "../../auth/uiGuidance";
import { useAuth } from "../../auth/hooks/useAuth";
import { TicketCard } from "../components/TicketCard";
import { TicketFiltersDialog } from "../components/TicketFiltersDialog";
import { TicketSearchField } from "../components/TicketSearchField";
import { TicketSortMenu } from "../components/TicketSortMenu";
import { countActiveFilters } from "../hooks/ticketListParams";
import { useTicketListParams } from "../hooks/useTicketListParams";
import { useTicketList } from "../hooks/useTickets";
import type { TicketTab } from "../types/ticket.types";

/** A message left by the previous screen, e.g. after forwarding a ticket to another Department. */
type TicketListLocationState = { notice?: string } | null;

export function TicketListPage() {
  const { user } = useAuth();
  const location = useLocation();
  const { params, updateParams } = useTicketListParams();
  const ticketListQuery = useTicketList(params);
  const [isFiltersDialogOpen, setIsFiltersDialogOpen] = useState(false);
  const [isNoticeDismissed, setIsNoticeDismissed] = useState(false);

  const notice = (location.state as TicketListLocationState)?.notice;
  const activeFilterCount = countActiveFilters(params);
  const hasSearchOrFilters = activeFilterCount > 0 || params.search !== undefined;

  // While the next page loads, the previous page is shown as a placeholder.
  const isShowingPlaceholder = ticketListQuery.isPlaceholderData;
  const tickets = ticketListQuery.data?.results ?? [];
  const totalCount = ticketListQuery.data?.count ?? 0;
  const pageCount = Math.max(1, Math.ceil(totalCount / params.pageSize));
  const firstShownNumber = (params.page - 1) * params.pageSize + 1;
  const lastShownNumber = firstShownNumber + tickets.length - 1;

  function clearSearchAndFilters() {
    updateParams({
      search: undefined,
      clientId: undefined,
      departmentId: undefined,
      facilityManagerId: undefined,
      workflowStage: undefined,
    });
  }

  function renderResults() {
    if (ticketListQuery.isPending) {
      return <LoadingIndicator label="Loading tickets" />;
    }
    if (ticketListQuery.isError) {
      const pageIsOutOfRange = parseApiError(ticketListQuery.error).details.page !== undefined;
      if (pageIsOutOfRange) {
        return (
          <Alert
            severity="warning"
            action={
              <Button color="inherit" size="small" onClick={() => updateParams({ page: 1 })}>
                Go to first page
              </Button>
            }
          >
            That page does not exist. The list may have changed.
          </Alert>
        );
      }
      return (
        <ErrorMessage
          error={ticketListQuery.error}
          title="Could not load tickets."
          onRetry={() => void ticketListQuery.refetch()}
        />
      );
    }
    if (tickets.length === 0) {
      return (
        <div className="flex flex-col items-center gap-3 p-8 text-center">
          <Typography>
            {hasSearchOrFilters
              ? "No tickets match your search or filters."
              : `There are no ${params.tab} tickets to show.`}
          </Typography>
          {hasSearchOrFilters && <Button onClick={clearSearchAndFilters}>Clear search and filters</Button>}
        </div>
      );
    }
    return (
      <>
        <ul className="m-0 flex list-none flex-col gap-3 p-0" aria-busy={isShowingPlaceholder}>
          {tickets.map((ticket) => (
            <li key={ticket.id} className={isShowingPlaceholder ? "opacity-50" : undefined}>
              <TicketCard ticket={ticket} />
            </li>
          ))}
        </ul>
        <div className="flex flex-col items-center justify-between gap-2 sm:flex-row">
          <Typography variant="body2" color="text.secondary" role="status">
            {isShowingPlaceholder
              ? "Loading page…"
              : `Showing ${firstShownNumber}–${lastShownNumber} of ${totalCount} tickets`}
          </Typography>
          <Pagination
            count={pageCount}
            page={params.page}
            disabled={isShowingPlaceholder}
            onChange={(_event, newPage) => updateParams({ page: newPage })}
            color="primary"
          />
        </div>
      </>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Typography component="h1" variant="h5">
          Tickets
        </Typography>
        {user && shouldOfferTicketCreation(user.role) && (
          <Button component={RouterLink} to="/tickets/new" variant="contained">
            Create New Ticket
          </Button>
        )}
      </div>

      {notice && !isNoticeDismissed && (
        <Alert severity="success" onClose={() => setIsNoticeDismissed(true)}>
          {notice}
        </Alert>
      )}

      <Tabs
        value={params.tab}
        onChange={(_event, newTab: TicketTab) => updateParams({ tab: newTab })}
        aria-label="Ticket tabs"
      >
        <Tab value="open" label="Open Tickets" />
        <Tab value="closed" label="Closed Tickets" />
      </Tabs>

      <div className="flex flex-wrap items-center gap-2">
        <TicketSearchField
          value={params.search ?? ""}
          onSearch={(searchText) => updateParams({ search: searchText || undefined }, { replace: true })}
        />
        <Badge badgeContent={activeFilterCount} color="primary">
          <Button variant="outlined" startIcon={<FilterListIcon />} onClick={() => setIsFiltersDialogOpen(true)}>
            Filters
          </Button>
        </Badge>
        <TicketSortMenu ordering={params.ordering} onChange={(ordering) => updateParams({ ordering })} />
      </div>

      <TicketFiltersDialog
        open={isFiltersDialogOpen}
        currentFilters={{
          clientId: params.clientId,
          departmentId: params.departmentId,
          facilityManagerId: params.facilityManagerId,
          workflowStage: params.workflowStage,
        }}
        onApply={(filters) => {
          setIsFiltersDialogOpen(false);
          updateParams(filters);
        }}
        onClose={() => setIsFiltersDialogOpen(false)}
      />

      <section aria-label={`${params.tab === "open" ? "Open" : "Closed"} tickets`} className="flex flex-col gap-3">
        {ticketListQuery.isFetching && !ticketListQuery.isPending && <LinearProgress aria-label="Refreshing tickets" />}
        {renderResults()}
      </section>
    </div>
  );
}

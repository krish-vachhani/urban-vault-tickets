import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import { useState } from "react";

import { ErrorMessage } from "../../../shared/components/ErrorMessage";
import { LoadingIndicator } from "../../../shared/components/LoadingIndicator";
import { useTicketFilterOptions } from "../hooks/useTickets";
import type { TicketListParams, WorkflowStage } from "../types/ticket.types";

export type TicketFilterValues = Pick<
  TicketListParams,
  "clientId" | "departmentId" | "facilityManagerId" | "workflowStage"
>;

type TicketFiltersDialogProps = {
  open: boolean;
  currentFilters: TicketFilterValues;
  onApply: (filters: TicketFilterValues) => void;
  onClose: () => void;
};

const ALL_OPTION_VALUE = "";

/** Every key is present (as undefined) so applying it overwrites, rather than keeps, the URL's filters. */
const NO_FILTERS: TicketFilterValues = {
  clientId: undefined,
  departmentId: undefined,
  facilityManagerId: undefined,
  workflowStage: undefined,
};

function toNumberOrUndefined(selectValue: string): number | undefined {
  return selectValue === ALL_OPTION_VALUE ? undefined : Number(selectValue);
}

/** The four assignment-required filters. Options come from the tickets this user can see. */
export function TicketFiltersDialog({ open, currentFilters, onApply, onClose }: TicketFiltersDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs" aria-labelledby="ticket-filters-title">
      <DialogTitle id="ticket-filters-title">Filters</DialogTitle>
      {/* Mounted only while open, so the selections restart from the URL's values each time. */}
      <FiltersForm currentFilters={currentFilters} onApply={onApply} onClose={onClose} />
    </Dialog>
  );
}

type FiltersFormProps = Omit<TicketFiltersDialogProps, "open">;

function FiltersForm({ currentFilters, onApply, onClose }: FiltersFormProps) {
  const filterOptionsQuery = useTicketFilterOptions();
  const [draftFilters, setDraftFilters] = useState<TicketFilterValues>(currentFilters);

  if (filterOptionsQuery.isPending) {
    return (
      <DialogContent>
        <LoadingIndicator label="Loading filter options" />
      </DialogContent>
    );
  }
  if (filterOptionsQuery.isError) {
    return (
      <DialogContent>
        <ErrorMessage
          error={filterOptionsQuery.error}
          title="Could not load the filters."
          onRetry={() => void filterOptionsQuery.refetch()}
        />
      </DialogContent>
    );
  }

  const options = filterOptionsQuery.data;

  return (
    <>
      <DialogContent className="flex flex-col gap-4 pt-2">
        <TextField
          select
          fullWidth
          label="Client"
          value={draftFilters.clientId ?? ALL_OPTION_VALUE}
          onChange={(event) =>
            setDraftFilters({ ...draftFilters, clientId: toNumberOrUndefined(event.target.value) })
          }
        >
          <MenuItem value={ALL_OPTION_VALUE}>All clients</MenuItem>
          {options.clients.map((client) => (
            <MenuItem key={client.id} value={client.id}>
              {client.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          fullWidth
          label="Department"
          value={draftFilters.departmentId ?? ALL_OPTION_VALUE}
          onChange={(event) =>
            setDraftFilters({ ...draftFilters, departmentId: toNumberOrUndefined(event.target.value) })
          }
        >
          <MenuItem value={ALL_OPTION_VALUE}>All departments</MenuItem>
          {options.departments.map((department) => (
            <MenuItem key={department.id} value={department.id}>
              {department.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          fullWidth
          label="Facility Manager"
          value={draftFilters.facilityManagerId ?? ALL_OPTION_VALUE}
          onChange={(event) =>
            setDraftFilters({ ...draftFilters, facilityManagerId: toNumberOrUndefined(event.target.value) })
          }
        >
          <MenuItem value={ALL_OPTION_VALUE}>All facility managers</MenuItem>
          {options.facility_managers.map((manager) => (
            <MenuItem key={manager.id} value={manager.id}>
              {manager.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          fullWidth
          label="Ticket status"
          value={draftFilters.workflowStage ?? ALL_OPTION_VALUE}
          onChange={(event) =>
            setDraftFilters({
              ...draftFilters,
              workflowStage: event.target.value === ALL_OPTION_VALUE ? undefined : (event.target.value as WorkflowStage),
            })
          }
        >
          <MenuItem value={ALL_OPTION_VALUE}>All statuses</MenuItem>
          {options.workflow_stages.map((stage) => (
            <MenuItem key={stage.value} value={stage.value}>
              {stage.label}
            </MenuItem>
          ))}
        </TextField>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setDraftFilters(NO_FILTERS)}>Clear all</Button>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => onApply(draftFilters)}>
          Apply
        </Button>
      </DialogActions>
    </>
  );
}

import { zodResolver } from "@hookform/resolvers/zod";
import Alert from "@mui/material/Alert";
import Autocomplete from "@mui/material/Autocomplete";
import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useRef, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";

import { parseApiError } from "../../../shared/api/apiError";
import { ErrorMessage } from "../../../shared/components/ErrorMessage";
import { FormSelectField } from "../../../shared/components/FormSelectField";
import { FormTextField } from "../../../shared/components/FormTextField";
import { LoadingIndicator } from "../../../shared/components/LoadingIndicator";
import type { UserRole } from "../../../shared/types/api.types";
import { applyServerFieldErrors } from "../../../shared/utils/applyServerFieldErrors";
import {
  useClientOffices,
  useMyClients,
  useOfficeFloors,
  useQuickIssues,
} from "../../reference-data/hooks/useReferenceData";
import { useCreateTicket } from "../hooks/useTicketMutations";
import {
  buildCreateTicketPayload,
  createTicketFormSchema,
  type IssueOption,
  type TicketFormValues,
} from "../schemas/createTicketSchema";
import type { TicketDetail } from "../types/ticket.types";
import { FloorAutocomplete } from "./FloorAutocomplete";
import { IssueAutocomplete } from "./IssueAutocomplete";
import { QuickIssueChips } from "./QuickIssueChips";

type TicketFormProps = {
  /** The signed-in user's role: Clients may omit the description, internal employees may not. */
  role: UserRole;
  onCreated: (ticket: TicketDetail) => void;
  onCancel: () => void;
};

const MULTIPLE_FLOORS_THRESHOLD = 1;

/**
 * Ticket creation for Clients, Facility Managers, and Department POCs. The Client, Office, and
 * Floor controls appear only when the user's data makes a choice necessary, and each depends on
 * the one before it.
 */
export function TicketForm({ role, onCreated, onCancel }: TicketFormProps) {
  const isDescriptionRequired = role !== "CLIENT";
  const [formError, setFormError] = useState<string | null>(null);
  const submissionInFlight = useRef(false);

  const { control, handleSubmit, setValue, getValues, resetField, setError } = useForm<TicketFormValues>({
    // The Floor rule depends on the Office chosen in this same form, so the schema is built at
    // validation time from the Floors currently on screen (see `needsFloorSelection` below).
    resolver: (values, validationContext, options) =>
      zodResolver(createTicketFormSchema({ isDescriptionRequired, isFloorSelectionRequired: needsFloorSelection }))(
        values,
        validationContext,
        options,
      ),
    defaultValues: { floorIds: [], issues: [], description: "" },
  });

  const selectedClientId = useWatch({ control, name: "clientId" }) ?? null;
  const selectedOfficeId = useWatch({ control, name: "clientOfficeId" }) ?? null;
  const selectedIssues = useWatch({ control, name: "issues" });
  const selectedFloorIds = useWatch({ control, name: "floorIds" });

  const clientsQuery = useMyClients();
  const officesQuery = useClientOffices(selectedClientId);
  const floorsQuery = useOfficeFloors(selectedOfficeId);
  const quickIssuesQuery = useQuickIssues(selectedClientId);
  const createTicketMutation = useCreateTicket();

  const clients = clientsQuery.data;
  const offices = officesQuery.data;
  const floors = floorsQuery.data;
  // The API attaches a single Floor itself, and a floor-less Office takes none, so the Floor
  // control (and its validation) exists only when there is a real choice to make.
  const needsFloorSelection = floors !== undefined && floors.length > MULTIPLE_FLOORS_THRESHOLD;

  // A single Client or Office is chosen for the user instead of asking.
  useEffect(() => {
    if (clients?.length === 1 && getValues("clientId") === undefined) {
      setValue("clientId", clients[0]!.id);
    }
  }, [clients, getValues, setValue]);
  useEffect(() => {
    if (offices?.length === 1 && getValues("clientOfficeId") === undefined) {
      setValue("clientOfficeId", offices[0]!.id);
    }
  }, [offices, getValues, setValue]);

  // Changing a parent choice clears everything chosen under it, so stale ids are never submitted.
  function handleClientChange() {
    resetField("clientOfficeId");
    setValue("floorIds", []);
    setValue("issues", []);
  }
  function handleOfficeChange() {
    setValue("floorIds", []);
  }

  function addIssue(issue: IssueOption) {
    setValue("issues", [...selectedIssues, issue], { shouldValidate: true });
  }

  function createTicket(values: TicketFormValues) {
    // Form validation is asynchronous: two rapid submits can finish before the disabled button renders.
    if (submissionInFlight.current) {
      return;
    }
    submissionInFlight.current = true;
    setFormError(null);
    createTicketMutation.mutate(
      { clientId: values.clientId, payload: buildCreateTicketPayload(values, needsFloorSelection) },
      {
        onSuccess: (createdTicket) => onCreated(createdTicket),
        onError: (error) =>
          setFormError(
            applyServerFieldErrors(parseApiError(error), setError, {
              client_office_id: "clientOfficeId",
              issue_ids: "issues",
              floor_ids: "floorIds",
              description: "description",
            }),
          ),
        onSettled: () => {
          submissionInFlight.current = false;
        },
      },
    );
  }

  if (clientsQuery.isPending) {
    return <LoadingIndicator label="Loading your clients" />;
  }
  if (clientsQuery.isError) {
    return (
      <ErrorMessage
        error={clientsQuery.error}
        title="Could not load your clients."
        onRetry={() => void clientsQuery.refetch()}
      />
    );
  }
  if (clientsQuery.data.length === 0) {
    return <Alert severity="warning">You are not linked to any client, so you cannot create tickets.</Alert>;
  }

  const selectedClient = clientsQuery.data.find((client) => client.id === selectedClientId);
  const selectedOffice = offices?.find((office) => office.id === selectedOfficeId);
  const isOfficeListLoading = selectedClientId !== null && officesQuery.isPending;
  const isFloorListLoading = selectedOfficeId !== null && floorsQuery.isPending;

  return (
    <form className="flex flex-col gap-4" noValidate onSubmit={(event) => void handleSubmit(createTicket)(event)}>
      {formError && <Alert severity="error">{formError}</Alert>}

      {clientsQuery.data.length > 1 ? (
        <Controller
          control={control}
          name="clientId"
          render={({ field, fieldState }) => (
            <Autocomplete
              options={clientsQuery.data}
              value={selectedClient ?? null}
              onChange={(_event, client) => {
                field.onChange(client?.id);
                handleClientChange();
              }}
              onBlur={field.onBlur}
              getOptionLabel={(client) => client.name}
              isOptionEqualToValue={(option, value) => option.id === value.id}
              renderInput={(inputProps) => (
                <TextField
                  {...inputProps}
                  inputRef={field.ref}
                  label="Client"
                  placeholder="Type or search client"
                  required
                  error={fieldState.invalid}
                  helperText={fieldState.error?.message}
                />
              )}
            />
          )}
        />
      ) : (
        <Typography>Client: {clientsQuery.data[0]?.name}</Typography>
      )}

      {isOfficeListLoading && <LoadingIndicator label="Loading offices" />}
      {officesQuery.isError && (
        <ErrorMessage
          error={officesQuery.error}
          title="Could not load the offices."
          onRetry={() => void officesQuery.refetch()}
        />
      )}
      {offices?.length === 0 && (
        <Alert severity="warning">
          There are no offices available to you for {selectedClient?.name ?? "this client"}.
        </Alert>
      )}
      {offices && offices.length > 1 && (
        <FormSelectField
          control={control}
          name="clientOfficeId"
          label="Office"
          options={offices}
          onValueChange={handleOfficeChange}
        />
      )}
      {offices?.length === 1 && <Typography>Office: {offices[0]?.name}</Typography>}

      {selectedOffice && (
        <>
          {quickIssuesQuery.isPending && <LoadingIndicator label="Loading quick issues" />}
          {quickIssuesQuery.isError && (
            <ErrorMessage
              error={quickIssuesQuery.error}
              title="Could not load quick issues."
              onRetry={() => void quickIssuesQuery.refetch()}
            />
          )}
          <QuickIssueChips
            quickIssues={quickIssuesQuery.data ?? []}
            selectedIssues={selectedIssues}
            onSelectIssue={addIssue}
          />

          <Controller
            control={control}
            name="issues"
            render={({ field, fieldState }) => (
              <IssueAutocomplete
                selectedIssues={field.value}
                onChange={field.onChange}
                errorMessage={fieldState.error?.message}
              />
            )}
          />

          {isFloorListLoading && <LoadingIndicator label="Loading floors" />}
          {floorsQuery.isError && (
            <ErrorMessage
              error={floorsQuery.error}
              title="Could not load the floors."
              onRetry={() => void floorsQuery.refetch()}
            />
          )}
          {needsFloorSelection && (
            <Controller
              control={control}
              name="floorIds"
              render={({ field, fieldState }) => (
                <FloorAutocomplete
                  floors={floors}
                  selectedFloorIds={selectedFloorIds}
                  onChange={field.onChange}
                  errorMessage={fieldState.error?.message}
                />
              )}
            />
          )}

          <FormTextField
            control={control}
            name="description"
            label={isDescriptionRequired ? "Description" : "Description (optional)"}
            placeholder="Describe the issue"
            required={isDescriptionRequired}
            multiline
            minRows={3}
          />
        </>
      )}

      <div className="flex justify-end gap-2">
        <Button onClick={onCancel} disabled={createTicketMutation.isPending}>
          Cancel
        </Button>
        <Button
          type="submit"
          variant="contained"
          disabled={createTicketMutation.isPending || isOfficeListLoading || isFloorListLoading}
        >
          {createTicketMutation.isPending ? "Submitting…" : "Submit"}
        </Button>
      </div>
    </form>
  );
}

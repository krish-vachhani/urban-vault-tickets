import { zodResolver } from "@hookform/resolvers/zod";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { parseApiError } from "../../../../shared/api/apiError";
import { ErrorMessage } from "../../../../shared/components/ErrorMessage";
import { FormSelectField } from "../../../../shared/components/FormSelectField";
import { LoadingIndicator } from "../../../../shared/components/LoadingIndicator";
import { applyServerFieldErrors } from "../../../../shared/utils/applyServerFieldErrors";
import { useEligibleWorkers } from "../../hooks/useEligibleWorkers";
import { useAssignWorker } from "../../hooks/useTicketMutations";
import { assignWorkerSchema, type AssignWorkerFormValues } from "../../schemas/ticketActionSchemas";

type AssignWorkerFormProps = {
  ticketId: number;
  onSuccess: (message: string) => void;
};

/** Department POC: pick one of the Department's Workers for this ticket. */
export function AssignWorkerForm({ ticketId, onSuccess }: AssignWorkerFormProps) {
  const eligibleWorkersQuery = useEligibleWorkers(ticketId);
  const assignWorkerMutation = useAssignWorker(ticketId);
  const [formError, setFormError] = useState<string | null>(null);
  const { control, handleSubmit, setError } = useForm<AssignWorkerFormValues>({
    resolver: zodResolver(assignWorkerSchema),
    defaultValues: {},
  });

  function assign(values: AssignWorkerFormValues) {
    setFormError(null);
    assignWorkerMutation.mutate(values.workerId, {
      onSuccess: (result) => onSuccess(result.message),
      onError: (error) =>
        setFormError(applyServerFieldErrors(parseApiError(error), setError, { worker_id: "workerId" })),
    });
  }

  if (eligibleWorkersQuery.isPending) {
    return <LoadingIndicator label="Loading workers" />;
  }
  if (eligibleWorkersQuery.isError) {
    return (
      <ErrorMessage
        error={eligibleWorkersQuery.error}
        title="Could not load the workers."
        onRetry={() => void eligibleWorkersQuery.refetch()}
      />
    );
  }

  const workerOptions = eligibleWorkersQuery.data.map((worker) => ({
    id: worker.id,
    name: `${worker.name} (${worker.role_label})`,
  }));

  if (workerOptions.length === 0) {
    return <Alert severity="warning">This department has no workers available to assign.</Alert>;
  }

  return (
    <form className="flex flex-col gap-3" noValidate onSubmit={(event) => void handleSubmit(assign)(event)}>
      {formError && <Alert severity="error">{formError}</Alert>}
      <FormSelectField control={control} name="workerId" label="Select worker" options={workerOptions} />
      <div>
        <Button type="submit" variant="contained" disabled={assignWorkerMutation.isPending}>
          {assignWorkerMutation.isPending ? "Assigning…" : "Ok"}
        </Button>
      </div>
    </form>
  );
}

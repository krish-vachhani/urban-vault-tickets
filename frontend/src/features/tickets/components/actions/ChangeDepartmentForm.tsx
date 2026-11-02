import { zodResolver } from "@hookform/resolvers/zod";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router";

import { parseApiError } from "../../../../shared/api/apiError";
import { ErrorMessage } from "../../../../shared/components/ErrorMessage";
import { FormSelectField } from "../../../../shared/components/FormSelectField";
import { FormTextField } from "../../../../shared/components/FormTextField";
import { LoadingIndicator } from "../../../../shared/components/LoadingIndicator";
import { applyServerFieldErrors } from "../../../../shared/utils/applyServerFieldErrors";
import { useDepartments } from "../../../reference-data/hooks/useReferenceData";
import { useChangeDepartment } from "../../hooks/useTicketMutations";
import { changeDepartmentSchema, type ChangeDepartmentFormValues } from "../../schemas/ticketActionSchemas";

type ChangeDepartmentFormProps = {
  ticketId: number;
  currentDepartmentId: number;
};

/** Department POC: forward the ticket to another Department with a required note. */
export function ChangeDepartmentForm({ ticketId, currentDepartmentId }: ChangeDepartmentFormProps) {
  const navigate = useNavigate();
  const departmentsQuery = useDepartments();
  const changeDepartmentMutation = useChangeDepartment(ticketId);
  const [formError, setFormError] = useState<string | null>(null);
  const { control, handleSubmit, setError } = useForm<ChangeDepartmentFormValues>({
    resolver: zodResolver(changeDepartmentSchema),
    defaultValues: { forwardingNote: "" },
  });

  function forward(values: ChangeDepartmentFormValues) {
    setFormError(null);
    changeDepartmentMutation.mutate(values, {
      // The forwarding POC no longer sees this ticket once it is in another Department,
      // so leave the detail page instead of reloading a ticket that is now out of scope.
      onSuccess: (result) =>
        void navigate("/tickets", {
          state: { notice: `Ticket forwarded to the ${result.current_department.name} department.` },
        }),
      onError: (error) =>
        setFormError(
          applyServerFieldErrors(parseApiError(error), setError, {
            department_id: "departmentId",
            forwarding_note: "forwardingNote",
          }),
        ),
    });
  }

  if (departmentsQuery.isPending) {
    return <LoadingIndicator label="Loading departments" />;
  }
  if (departmentsQuery.isError) {
    return (
      <ErrorMessage
        error={departmentsQuery.error}
        title="Could not load the departments."
        onRetry={() => void departmentsQuery.refetch()}
      />
    );
  }

  // The API also rejects the current Department; leaving it out just avoids a pointless choice.
  const destinationOptions = departmentsQuery.data.filter((department) => department.id !== currentDepartmentId);

  return (
    <form className="flex flex-col gap-3" noValidate onSubmit={(event) => void handleSubmit(forward)(event)}>
      {formError && <Alert severity="error">{formError}</Alert>}
      <FormSelectField control={control} name="departmentId" label="Select department" options={destinationOptions} />
      <FormTextField control={control} name="forwardingNote" label="Forwarding note" multiline minRows={2} required />
      <div>
        <Button type="submit" variant="contained" disabled={changeDepartmentMutation.isPending}>
          {changeDepartmentMutation.isPending ? "Forwarding…" : "Ok"}
        </Button>
      </div>
    </form>
  );
}

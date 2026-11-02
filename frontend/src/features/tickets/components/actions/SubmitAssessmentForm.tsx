import { zodResolver } from "@hookform/resolvers/zod";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import FormControl from "@mui/material/FormControl";
import FormControlLabel from "@mui/material/FormControlLabel";
import FormHelperText from "@mui/material/FormHelperText";
import FormLabel from "@mui/material/FormLabel";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
import Typography from "@mui/material/Typography";
import { useRef, useState } from "react";
import { useController, useForm } from "react-hook-form";

import { parseApiError } from "../../../../shared/api/apiError";
import { applyServerFieldErrors } from "../../../../shared/utils/applyServerFieldErrors";
import { useSubmitAssessment } from "../../hooks/useTicketMutations";
import { assessmentSchema, type AssessmentFormValues } from "../../schemas/ticketActionSchemas";
import type { AssessmentOutcome } from "../../types/ticket.types";
import { ASSESSMENT_OUTCOME_DESCRIPTIONS, ASSESSMENT_OUTCOME_LABELS } from "../../types/ticketLabels";

type SubmitAssessmentFormProps = {
  ticketId: number;
  onSuccess: (message: string) => void;
};

const OUTCOMES: AssessmentOutcome[] = ["FULLY_RESOLVED", "PARTIALLY_RESOLVED", "CHANGE_REQUESTED"];

/** Assigned Worker: choose exactly one of the three assessment outcomes. */
export function SubmitAssessmentForm({ ticketId, onSuccess }: SubmitAssessmentFormProps) {
  const submitAssessmentMutation = useSubmitAssessment(ticketId);
  const [formError, setFormError] = useState<string | null>(null);
  const submissionInFlight = useRef(false);
  const { control, handleSubmit, setError } = useForm<AssessmentFormValues>({
    resolver: zodResolver(assessmentSchema),
    defaultValues: {},
  });
  const { field, fieldState } = useController({ name: "outcome", control });

  function submit(values: AssessmentFormValues) {
    if (submissionInFlight.current) {
      return;
    }
    submissionInFlight.current = true;
    setFormError(null);
    submitAssessmentMutation.mutate(values.outcome, {
      onSuccess: () => onSuccess("Assessment submitted. The ticket is now waiting for Department POC review."),
      onError: (error) =>
        setFormError(applyServerFieldErrors(parseApiError(error), setError, { outcome: "outcome" })),
      onSettled: () => {
        submissionInFlight.current = false;
      },
    });
  }

  return (
    <form className="flex flex-col gap-3" noValidate onSubmit={(event) => void handleSubmit(submit)(event)}>
      {formError && <Alert severity="error">{formError}</Alert>}
      <FormControl error={fieldState.invalid}>
        <FormLabel id="assessment-outcome-label">Assessment</FormLabel>
        <RadioGroup
          aria-labelledby="assessment-outcome-label"
          name={field.name}
          value={field.value ?? ""}
          onChange={(event) => field.onChange(event.target.value)}
        >
          {OUTCOMES.map((outcome) => (
            <FormControlLabel
              key={outcome}
              value={outcome}
              control={<Radio />}
              label={
                <span>
                  {ASSESSMENT_OUTCOME_LABELS[outcome]}
                  <Typography component="span" variant="body2" color="text.secondary" className="block">
                    {ASSESSMENT_OUTCOME_DESCRIPTIONS[outcome]}
                  </Typography>
                </span>
              }
              className="items-start"
            />
          ))}
        </RadioGroup>
        {fieldState.error && <FormHelperText>{fieldState.error.message}</FormHelperText>}
      </FormControl>
      <div>
        <Button type="submit" variant="contained" disabled={submitAssessmentMutation.isPending}>
          {submitAssessmentMutation.isPending ? "Submitting…" : "Submit"}
        </Button>
      </div>
    </form>
  );
}

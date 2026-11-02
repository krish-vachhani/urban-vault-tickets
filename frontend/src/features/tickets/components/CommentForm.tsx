import { zodResolver } from "@hookform/resolvers/zod";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Paper from "@mui/material/Paper";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { parseApiError } from "../../../shared/api/apiError";
import { FormTextField } from "../../../shared/components/FormTextField";
import { applyServerFieldErrors } from "../../../shared/utils/applyServerFieldErrors";
import { useAddComment } from "../hooks/useTicketMutations";
import { commentSchema, type CommentFormValues } from "../schemas/ticketActionSchemas";

type CommentFormProps = {
  ticketId: number;
  onCommentPosted: () => void;
};

/** The "Write a comment / Post" box. It stays pinned to the bottom of the screen on the detail page. */
export function CommentForm({ ticketId, onCommentPosted }: CommentFormProps) {
  const addCommentMutation = useAddComment(ticketId);
  const [formError, setFormError] = useState<string | null>(null);
  const { control, handleSubmit, setError, reset } = useForm<CommentFormValues>({
    resolver: zodResolver(commentSchema),
    defaultValues: { body: "" },
  });

  function postComment(values: CommentFormValues) {
    setFormError(null);
    addCommentMutation.mutate(values.body, {
      onSuccess: () => {
        reset();
        onCommentPosted();
      },
      onError: (error) => setFormError(applyServerFieldErrors(parseApiError(error), setError, { body: "body" })),
    });
  }

  return (
    <Paper
      component="form"
      elevation={4}
      noValidate
      aria-label="Add a comment"
      className="sticky bottom-0 z-10 flex flex-col gap-2 p-3"
      onSubmit={(event: React.FormEvent<HTMLFormElement>) => void handleSubmit(postComment)(event)}
    >
      {formError && <Alert severity="error">{formError}</Alert>}
      <div className="flex items-start gap-2">
        <FormTextField control={control} name="body" label="Write a comment" multiline maxRows={4} size="small" />
        <Button type="submit" variant="contained" disabled={addCommentMutation.isPending}>
          {addCommentMutation.isPending ? "Posting…" : "Post"}
        </Button>
      </div>
    </Paper>
  );
}

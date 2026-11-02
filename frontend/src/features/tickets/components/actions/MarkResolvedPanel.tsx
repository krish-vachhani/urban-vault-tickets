import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";

import { parseApiError } from "../../../../shared/api/apiError";
import { useMarkResolved } from "../../hooks/useTicketMutations";

type MarkResolvedPanelProps = {
  ticketId: number;
  onSuccess: (message: string) => void;
};

/** Client (or the ticket's creator): confirm that the issue is resolved and close the ticket. */
export function MarkResolvedPanel({ ticketId, onSuccess }: MarkResolvedPanelProps) {
  const markResolvedMutation = useMarkResolved(ticketId);

  function markResolved() {
    markResolvedMutation.mutate(undefined, {
      onSuccess: () => onSuccess("Ticket marked as resolved and moved to Closed Tickets."),
    });
  }

  return (
    <div className="flex flex-col gap-3">
      {markResolvedMutation.isError && (
        <Alert severity="error">{parseApiError(markResolvedMutation.error).message}</Alert>
      )}
      <Typography>If the issue no longer persists, you can mark it as resolved.</Typography>
      <div>
        <Button variant="contained" onClick={markResolved} disabled={markResolvedMutation.isPending}>
          {markResolvedMutation.isPending ? "Submitting…" : "Submit"}
        </Button>
      </div>
    </div>
  );
}

import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Paper from "@mui/material/Paper";
import Snackbar from "@mui/material/Snackbar";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { Link as RouterLink, useLocation, useParams } from "react-router";

import { parseApiError } from "../../../shared/api/apiError";
import { ErrorMessage } from "../../../shared/components/ErrorMessage";
import { LoadingIndicator } from "../../../shared/components/LoadingIndicator";
import { TicketActions } from "../components/TicketActions";
import { TicketActivity } from "../components/TicketActivity";
import { TicketHeader } from "../components/TicketHeader";
import { useTicket } from "../hooks/useTickets";

/** Set by the Create Ticket screen so this page can show the wireframe's "created successfully" banner. */
type TicketDetailLocationState = { justCreated?: boolean } | null;

const HTTP_NOT_FOUND = 404;

function BackToTicketsLink() {
  return (
    <Button component={RouterLink} to="/tickets" startIcon={<ArrowBackIcon />} className="self-start">
      Back to tickets
    </Button>
  );
}

export function TicketDetailPage() {
  const { ticketId: ticketIdParam } = useParams();
  const location = useLocation();
  const ticketId = Number(ticketIdParam);
  const ticketQuery = useTicket(ticketId);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const wasJustCreated = (location.state as TicketDetailLocationState)?.justCreated === true;

  // A 404 means the ticket is gone from this user's view (e.g. forwarded to another Department),
  // so it replaces any cached copy. Other refetch failures keep showing the ticket already loaded.
  const isNotFound = ticketQuery.isError && parseApiError(ticketQuery.error).status === HTTP_NOT_FOUND;
  if (ticketQuery.data === undefined || isNotFound) {
    if (ticketQuery.isPending) {
      return <LoadingIndicator label="Loading ticket" />;
    }
    return (
      <div className="flex flex-col gap-3">
        <BackToTicketsLink />
        {isNotFound ? (
          <Paper variant="outlined" className="p-6">
            <Typography component="h1" variant="h6">
              Ticket not found
            </Typography>
            <Typography color="text.secondary">
              This ticket does not exist, or you do not have access to it.
            </Typography>
          </Paper>
        ) : (
          <ErrorMessage
            error={ticketQuery.error}
            title="Could not load the ticket."
            onRetry={() => void ticketQuery.refetch()}
          />
        )}
      </div>
    );
  }

  const ticket = ticketQuery.data;

  return (
    <div className="flex flex-col gap-4">
      <BackToTicketsLink />

      {wasJustCreated && ticket.status !== "CLOSED" && (
        <Alert severity="success">
          Ticket created successfully. If the issue is resolved, you can mark it as resolved.
        </Alert>
      )}

      {/* On tablets and up, the header and the user's call-to-action panel stay pinned to the top while
          scrolling. On a phone an open panel would fill the screen and hide the page below it, so they scroll. */}
      <div className="flex flex-col gap-2 bg-neutral-100 pb-2 sm:sticky sm:top-0 sm:z-20">
        <TicketHeader ticket={ticket} />
        <TicketActions ticket={ticket} onActionSucceeded={setSuccessMessage} />
      </div>

      <Paper component="section" aria-labelledby="issue-description-heading" variant="outlined" className="p-3">
        <Typography id="issue-description-heading" component="h2" variant="subtitle1" className="font-semibold">
          Issue Description
        </Typography>
        <Typography className="break-words whitespace-pre-wrap">
          {ticket.description || "No description was provided."}
        </Typography>
      </Paper>

      <TicketActivity ticketId={ticket.id} />

      <Snackbar
        open={successMessage !== null}
        autoHideDuration={6000}
        onClose={() => setSuccessMessage(null)}
        anchorOrigin={{ vertical: "top", horizontal: "center" }}
      >
        <Alert severity="success" onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      </Snackbar>
    </div>
  );
}

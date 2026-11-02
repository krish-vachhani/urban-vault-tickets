import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { Link as RouterLink } from "react-router";

import { formatDateTime } from "../../../shared/utils/formatDateTime";
import type { TicketSummary } from "../types/ticket.types";
import { WORKFLOW_STAGE_LABELS } from "../types/ticketLabels";
import { describeAssignees, describeIssues, describeLocation } from "../utils/ticketPresentation";

type TicketCardProps = {
  ticket: TicketSummary;
};

export function TicketCard({ ticket }: TicketCardProps) {
  return (
    <Paper component="article" variant="outlined" className="flex flex-col gap-2 p-3 sm:p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <Typography component="h3" variant="subtitle1" className="font-semibold">
            {describeIssues(ticket)}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {describeLocation(ticket)}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            #{ticket.ticket_number}
          </Typography>
        </div>
        <Button
          component={RouterLink}
          to={`/tickets/${ticket.id}`}
          variant="contained"
          color="success"
          size="small"
          aria-label={`View ${ticket.ticket_number}`}
        >
          View
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        <Chip size="small" variant="outlined" label={WORKFLOW_STAGE_LABELS[ticket.workflow_stage]} />
        {ticket.action_required && <Chip size="small" color="error" label="Action Required" />}
      </div>

      <Typography variant="body2">
        Created {formatDateTime(ticket.created_at)} · {ticket.created_by.name} ({ticket.created_by.role_label})
      </Typography>
      <Typography variant="body2">Current Assignee(s): {describeAssignees(ticket)}</Typography>
    </Paper>
  );
}

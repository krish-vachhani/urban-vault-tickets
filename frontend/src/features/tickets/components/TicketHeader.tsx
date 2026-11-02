import Chip from "@mui/material/Chip";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";

import { formatDateTime } from "../../../shared/utils/formatDateTime";
import type { TicketDetail, TicketStatus } from "../types/ticket.types";
import { WORKFLOW_STAGE_LABELS } from "../types/ticketLabels";
import { describeAssignees, describeIssues, describeLocation } from "../utils/ticketPresentation";

type TicketHeaderProps = {
  ticket: TicketDetail;
};

const STATUS_LABELS: Record<TicketStatus, string> = {
  OPEN: "Open",
  TECHNICIAN_CLOSED: "Technician Closed",
  CLOSED: "Closed",
};

export function TicketHeader({ ticket }: TicketHeaderProps) {
  return (
    <Paper component="header" variant="outlined" className="flex flex-col gap-1 p-3">
      <Typography component="h1" variant="h6">
        {describeIssues(ticket)}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {describeLocation(ticket)} · #{ticket.ticket_number}
      </Typography>
      <div className="flex flex-wrap gap-2 py-1">
        <Chip size="small" variant="outlined" label={WORKFLOW_STAGE_LABELS[ticket.workflow_stage]} />
        <Chip size="small" variant="outlined" label={`Status: ${STATUS_LABELS[ticket.status]}`} />
        {ticket.action_required && <Chip size="small" color="error" label="Action Required" />}
      </div>
      <Typography variant="body2">
        Created {formatDateTime(ticket.created_at)} · {ticket.created_by.name} ({ticket.created_by.role_label})
      </Typography>
      <Typography variant="body2">Current Assignee(s): {describeAssignees(ticket)}</Typography>
      {ticket.closed_at && ticket.closed_by && (
        <Typography variant="body2">
          Resolved {formatDateTime(ticket.closed_at)} · {ticket.closed_by.name} ({ticket.closed_by.role_label})
        </Typography>
      )}
    </Paper>
  );
}

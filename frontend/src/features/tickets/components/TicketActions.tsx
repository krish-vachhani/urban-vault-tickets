import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Paper from "@mui/material/Paper";
import { useState } from "react";

import type { TicketDetail } from "../types/ticket.types";
import { AssignWorkerForm } from "./actions/AssignWorkerForm";
import { ChangeDepartmentForm } from "./actions/ChangeDepartmentForm";
import { MarkResolvedPanel } from "./actions/MarkResolvedPanel";
import { SubmitAssessmentForm } from "./actions/SubmitAssessmentForm";

type TicketActionsProps = {
  ticket: TicketDetail;
  /** Called with a success message after an action completes. */
  onActionSucceeded: (message: string) => void;
};

type ActionPanel = "assign-worker" | "change-department" | "submit-assessment" | "mark-resolved";

/**
 * The call-to-action panel for the signed-in user. Which buttons appear comes from
 * the backend's `available_actions`; each button opens a form that calls its own
 * explicit API endpoint, and the backend re-checks permission when it is submitted.
 */
export function TicketActions({ ticket, onActionSucceeded }: TicketActionsProps) {
  const [openPanel, setOpenPanel] = useState<ActionPanel | null>(null);
  const actions = ticket.available_actions;

  const hasAnyAction =
    actions.can_assign_worker ||
    actions.can_change_department ||
    actions.can_submit_assessment ||
    actions.can_mark_resolved;
  if (!hasAnyAction) {
    return null;
  }

  function togglePanel(panel: ActionPanel) {
    setOpenPanel(openPanel === panel ? null : panel);
  }

  function handleSuccess(message: string) {
    setOpenPanel(null);
    onActionSucceeded(message);
  }

  function renderActionButton(panel: ActionPanel, label: string) {
    const isOpen = openPanel === panel;
    return (
      <Button
        variant={isOpen ? "contained" : "outlined"}
        aria-expanded={isOpen}
        aria-controls={`${panel}-panel`}
        onClick={() => togglePanel(panel)}
      >
        {label}
      </Button>
    );
  }

  return (
    <Paper component="section" aria-label="Ticket actions" variant="outlined" className="flex flex-col gap-3 p-3">
      {actions.can_assign_worker && (
        <Alert severity="info">A new ticket has been assigned to you. Review it and take the next action.</Alert>
      )}
      {actions.can_submit_assessment && (
        <Alert severity="info">You have been assigned this ticket. Take action.</Alert>
      )}

      <div className="flex flex-wrap gap-2">
        {actions.can_assign_worker && renderActionButton("assign-worker", "Assign Worker")}
        {actions.can_change_department && renderActionButton("change-department", "Change Department")}
        {actions.can_submit_assessment && renderActionButton("submit-assessment", "Submit Assessment")}
        {actions.can_mark_resolved && renderActionButton("mark-resolved", "Mark Resolved")}
      </div>

      {openPanel !== null && (
        <div id={`${openPanel}-panel`}>
          {openPanel === "assign-worker" && <AssignWorkerForm ticketId={ticket.id} onSuccess={handleSuccess} />}
          {openPanel === "change-department" && (
            <ChangeDepartmentForm ticketId={ticket.id} currentDepartmentId={ticket.current_department.id} />
          )}
          {openPanel === "submit-assessment" && (
            <SubmitAssessmentForm ticketId={ticket.id} onSuccess={handleSuccess} />
          )}
          {openPanel === "mark-resolved" && <MarkResolvedPanel ticketId={ticket.id} onSuccess={handleSuccess} />}
        </div>
      )}
    </Paper>
  );
}

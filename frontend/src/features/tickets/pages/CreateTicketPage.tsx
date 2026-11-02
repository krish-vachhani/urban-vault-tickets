import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { Link as RouterLink, useNavigate } from "react-router";

import { useAuth } from "../../auth/hooks/useAuth";
import { shouldOfferTicketCreation } from "../../auth/uiGuidance";
import { TicketForm } from "../components/TicketForm";

export function CreateTicketPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  if (!user) {
    return null;
  }

  if (!shouldOfferTicketCreation(user.role)) {
    return (
      <div className="flex flex-col items-start gap-3">
        <Alert severity="warning">You do not have permission to create tickets.</Alert>
        <Button component={RouterLink} to="/tickets" variant="contained">
          Back to tickets
        </Button>
      </div>
    );
  }

  return (
    <Paper component="section" aria-labelledby="create-ticket-heading" className="flex flex-col gap-4 p-4 sm:p-6">
      <Typography id="create-ticket-heading" component="h1" variant="h5">
        Create New Ticket
      </Typography>
      <TicketForm
        role={user.role}
        onCreated={(ticket) => void navigate(`/tickets/${ticket.id}`, { state: { justCreated: true } })}
        onCancel={() => void navigate("/tickets")}
      />
    </Paper>
  );
}

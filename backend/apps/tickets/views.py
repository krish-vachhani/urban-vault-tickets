from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.serializers import IdNameSerializer
from apps.tickets import selectors
from apps.tickets.exceptions import InvalidTicketTransition
from apps.tickets.models import Ticket, TicketStatus, WorkflowStage
from config.api_helpers import parse_id, results_response


class EligibleWorkersView(APIView):
    """Workers the current Department POC may pick from in the Assign Worker panel.

    Checks run in the documented order (README-api-conventions.md §3): visibility 404,
    then action permission 403, then Ticket state 409.
    """

    def get(self, request: Request, ticket_id: str) -> Response:
        visible_tickets = selectors.get_visible_tickets(request.user).select_related("current_department")
        ticket: Ticket = get_object_or_404(visible_tickets, pk=parse_id(ticket_id, "ticket_id"))

        if ticket.current_department.poc_user_id != request.user.id:
            raise PermissionDenied("Only the current Department POC can view eligible workers.")
        if ticket.workflow_stage != WorkflowStage.PENDING_TECHNICIAN_ASSIGNMENT or ticket.status != TicketStatus.OPEN:
            raise InvalidTicketTransition("The ticket is not awaiting worker assignment.")

        return results_response(IdNameSerializer, selectors.get_eligible_workers(ticket))

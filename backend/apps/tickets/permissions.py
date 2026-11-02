"""Who may act on a Ticket (the 403 rules), plus the UI hints derived from them.

Rules: readmes/README-authorization.md §3 and §4. Whether the Ticket's stage and status allow
an action (the 409 rules) lives on the Ticket model (is_awaiting_assessment and similar).

The predicates are shared by the DRF permission classes (checked before the request body is
validated), the services (re-checked after the Ticket row is locked), and the
available_actions / action_required hints, so the rules cannot drift apart.
"""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.models import User, UserRole
from apps.organizations.models import UserClient
from apps.tickets import selectors
from apps.tickets.models import Ticket, TicketAssignment, WorkflowStage

TICKET_CREATOR_ROLES = (UserRole.CLIENT, UserRole.FACILITY_MANAGER, UserRole.DEPARTMENT_POC)

NOT_ALLOWED_TO_CREATE_MESSAGE = "Your role cannot create tickets."
NOT_CURRENT_POC_MESSAGE = "Only the current Department POC can perform this action."
NOT_ASSIGNED_WORKER_MESSAGE = "Only the currently assigned worker can submit an assessment."
NOT_ALLOWED_TO_RESOLVE_MESSAGE = "Only a client user of this ticket's client, or the ticket's creator, can resolve it."


def is_current_department_poc(user: User, ticket: Ticket) -> bool:
    return ticket.current_department.poc_user_id == user.id


def is_assigned_worker(user: User, active_assignment: TicketAssignment | None) -> bool:
    return active_assignment is not None and active_assignment.worker_id == user.id


def can_mark_resolved(user: User, ticket: Ticket) -> bool:
    """The Ticket's creator, or a Client user mapped to the Client that owns the Ticket's Office."""
    if ticket.created_by_id == user.id:
        return True
    if user.role != UserRole.CLIENT:
        return False
    return UserClient.objects.filter(user=user, client_id=ticket.client_office.client_id).exists()


class CanCreateTickets(BasePermission):
    message = NOT_ALLOWED_TO_CREATE_MESSAGE

    def has_permission(self, request: Request, view: APIView) -> bool:
        return request.user.role in TICKET_CREATOR_ROLES


class IsCurrentDepartmentPoc(BasePermission):
    message = NOT_CURRENT_POC_MESSAGE

    def has_object_permission(self, request: Request, view: APIView, ticket: Ticket) -> bool:
        return is_current_department_poc(request.user, ticket)


class IsAssignedWorker(BasePermission):
    message = NOT_ASSIGNED_WORKER_MESSAGE

    def has_object_permission(self, request: Request, view: APIView, ticket: Ticket) -> bool:
        return is_assigned_worker(request.user, selectors.get_active_assignment(ticket))


class CanResolveTicket(BasePermission):
    message = NOT_ALLOWED_TO_RESOLVE_MESSAGE

    def has_object_permission(self, request: Request, view: APIView, ticket: Ticket) -> bool:
        return can_mark_resolved(request.user, ticket)


def get_available_actions(user: User, ticket: Ticket, active_assignment: TicketAssignment | None) -> dict[str, bool]:
    """UI guidance only: every action endpoint checks permission and state again."""
    is_poc = is_current_department_poc(user, ticket)
    return {
        "can_assign_worker": is_poc and ticket.is_awaiting_worker_assignment,
        "can_change_department": is_poc and ticket.is_awaiting_worker_assignment,
        "can_submit_assessment": is_assigned_worker(user, active_assignment) and ticket.is_awaiting_assessment,
        "can_mark_resolved": not ticket.is_closed and can_mark_resolved(user, ticket),
        "can_comment": True,
    }


def is_action_required(user: User, ticket: Ticket, active_assignment: TicketAssignment | None) -> bool:
    """Whether the Ticket is waiting on this user's workflow step (the red "Action Required" badge).

    Deliberately not derived from available_actions: the POC is waited on at the review stage,
    where no action exists, and Clients are never waited on even though they can resolve
    (readmes/README-ticket-listing-api.md §9).
    """
    if ticket.is_closed:
        return False
    if is_current_department_poc(user, ticket):
        return ticket.workflow_stage in (
            WorkflowStage.PENDING_TECHNICIAN_ASSIGNMENT,
            WorkflowStage.PENDING_DEPARTMENT_POC_REVIEW,
        )
    if is_assigned_worker(user, active_assignment):
        return ticket.workflow_stage == WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT
    return False

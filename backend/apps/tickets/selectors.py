"""Read-only Ticket queries: role-based visibility and Worker eligibility."""

from django.db.models import Exists, OuterRef, Q, QuerySet

from apps.accounts.models import User, UserRole
from apps.organizations.models import UserClient
from apps.tickets.models import Ticket, TicketAssignment


def get_visible_tickets(user: User) -> QuerySet[Ticket]:
    """Tickets the user may see: their role's rule OR Tickets they created.

    Rules: readmes/README-authorization.md §1. Each rule is a foreign-key condition or
    an Exists subquery, so no join can duplicate a Ticket row.
    """
    return Ticket.objects.filter(_get_role_visibility(user) | Q(created_by=user))


def _get_role_visibility(user: User) -> Q:
    if user.role == UserRole.CLIENT:
        mapped_to_ticket_client = UserClient.objects.filter(
            user=user, client_id=OuterRef("client_office__client_id")
        )
        return Q(Exists(mapped_to_ticket_client))
    if user.role == UserRole.FACILITY_MANAGER:
        return Q(client_office__property__facility_manager=user)
    if user.role == UserRole.DEPARTMENT_POC:
        return Q(current_department__poc_user=user)
    # Workers keep read-only visibility after they stop being the assignee.
    ever_assigned_to_user = TicketAssignment.objects.filter(ticket=OuterRef("pk"), worker=user)
    return Q(Exists(ever_assigned_to_user))


def get_eligible_workers(ticket: Ticket) -> QuerySet[User]:
    """Active Workers in the Ticket's current Department; no Property or workload filter."""
    return User.objects.filter(
        is_active=True,
        role=UserRole.WORKER,
        department_membership__department_id=ticket.current_department_id,
    ).order_by("name", "id")

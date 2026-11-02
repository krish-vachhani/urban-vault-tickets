"""Small builders for ticket test records. Tests never depend on the demo seed command."""

from apps.accounts.models import UserRole
from apps.organizations.tests.helpers import create_department, create_office, create_user
from apps.tickets.models import ActivityEventType, Ticket, TicketActivity


def create_ticket(**fields) -> Ticket:
    """Create a Ticket, building any related record the caller does not supply."""
    if "client_office" not in fields:
        fields["client_office"] = create_office()
    if "created_by" not in fields:
        fields["created_by"] = create_user(UserRole.CLIENT)
    if "origin_department" not in fields:
        fields["origin_department"] = create_department()
    fields.setdefault("current_department", fields["origin_department"])
    return Ticket.objects.create(**fields)


def create_activity(ticket: Ticket, **fields) -> TicketActivity:
    fields.setdefault("event_type", ActivityEventType.TICKET_CREATED)
    fields.setdefault("description", "created the ticket.")
    return TicketActivity.objects.create(ticket=ticket, **fields)

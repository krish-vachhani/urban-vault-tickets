"""Helpers for writing TicketActivity entries (readmes/README-audit-and-communication.md §2)."""

from apps.accounts.models import User
from apps.tickets.models import ActivityEventType, Ticket, TicketActivity


def build_change(field: str, from_value: str, to_value: str) -> dict[str, str]:
    """Build the display-ready before → after object the History view renders."""
    return {"field": field, "from": from_value, "to": to_value}


def record_activity(
    ticket: Ticket,
    actor: User | None,
    event_type: ActivityEventType,
    description: str,
    metadata: dict | None = None,
) -> TicketActivity:
    """Append an audit entry. Callers invoke this inside the transaction of the change it records."""
    return TicketActivity.objects.create(
        ticket=ticket, actor=actor, event_type=event_type, description=description, metadata=metadata or {}
    )

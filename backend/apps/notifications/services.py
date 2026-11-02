"""Creates the durable notification intent (outbox rows) for ticket actions.

Ticket services call this inside the same database transaction as the action, so the
intent exists if and only if the action commits. Publishing to Celery after commit and
delivering the notification are added in Phase 5 (readmes/README-async-processing.md).
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING

from apps.accounts.models import User
from apps.notifications.models import NotificationEventType, NotificationOutbox

if TYPE_CHECKING:
    from apps.tickets.models import Ticket, TicketActivity


def create_notifications(
    *,
    ticket: "Ticket",
    source_activity: "TicketActivity",
    event_type: NotificationEventType,
    recipients: Iterable[User],
    actor: User,
) -> list[NotificationOutbox]:
    """Queue one PENDING notification per distinct recipient, never notifying the actor."""
    distinct_recipients = {recipient.id: recipient for recipient in recipients if recipient.id != actor.id}
    outbox_rows = [
        NotificationOutbox(
            ticket=ticket,
            source_activity=source_activity,
            recipient=recipient,
            event_type=event_type,
            idempotency_key=f"activity:{source_activity.id}:recipient:{recipient.id}",
            payload={"ticket_id": ticket.id, "ticket_number": ticket.ticket_number},
        )
        for recipient in distinct_recipients.values()
    ]
    return NotificationOutbox.objects.bulk_create(outbox_rows)

"""Creates the durable notification intent (outbox rows) for ticket actions.

Ticket services call this inside the same database transaction as the action, so the
intent exists if and only if the action commits. Publishing to Celery happens only after
that commit; delivery is in processing.py (readmes/README-async-processing.md §6).
"""

from collections.abc import Iterable
from functools import partial
from typing import TYPE_CHECKING

from django.db import transaction

from apps.accounts.models import User
from apps.notifications.models import NotificationEventType, NotificationOutbox
from apps.notifications.publishing import publish_notification

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
    """Queue one PENDING notification per distinct recipient, never notifying the actor.

    Each row is published to Celery only after the surrounding transaction commits. If that
    transaction rolls back, the rows vanish and nothing is published.
    """
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
    created_rows = NotificationOutbox.objects.bulk_create(outbox_rows)
    for row in created_rows:
        # robust=True: a failure in one callback is logged and never fails the committed action.
        transaction.on_commit(partial(publish_notification, row.id), robust=True)
    return created_rows

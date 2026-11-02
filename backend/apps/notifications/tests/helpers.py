"""Builders for outbox rows. Tests never publish to a real broker or depend on the demo seed."""

from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import UserRole
from apps.notifications.constants import PROCESSING_LEASE
from apps.notifications.models import NotificationEventType, NotificationOutbox, OutboxStatus
from apps.organizations.tests.helpers import create_user
from apps.tickets.tests.helpers import create_activity, create_ticket


def create_outbox_row(**fields) -> NotificationOutbox:
    """Create a due, unpublished PENDING row with a matching Ticket, Activity, and recipient."""
    ticket = fields.pop("ticket", None) or create_ticket()
    source_activity = create_activity(ticket)
    recipient = fields.pop("recipient", None) or create_user(UserRole.WORKER)
    fields.setdefault("event_type", NotificationEventType.WORKER_ASSIGNED)
    fields.setdefault("idempotency_key", f"activity:{source_activity.id}:recipient:{recipient.id}")
    fields.setdefault("payload", {"ticket_id": ticket.id, "ticket_number": ticket.ticket_number})
    return NotificationOutbox.objects.create(
        ticket=ticket, source_activity=source_activity, recipient=recipient, **fields
    )


def make_due(row: NotificationOutbox) -> None:
    """Stand in for the backoff wait having passed."""
    NotificationOutbox.objects.filter(id=row.id).update(next_attempt_at=timezone.now() - timedelta(seconds=1))


def create_stale_processing_row(**fields) -> NotificationOutbox:
    """A row a worker claimed and then abandoned: PROCESSING for longer than the lease."""
    fields.setdefault("attempt_count", 1)
    return create_outbox_row(
        status=OutboxStatus.PROCESSING,
        processing_started_at=timezone.now() - PROCESSING_LEASE - timedelta(seconds=1),
        **fields,
    )

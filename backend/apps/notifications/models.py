"""The transactional notification outbox.

Schema reference: readmes/README-database-schema.md §2.18.
Delivery design: readmes/README-async-processing.md.

An outbox row is created in the same database transaction as the ticket action
that needs a notification, so PostgreSQL always remembers the intent to notify.
This module only defines the table; creating, dispatching, and delivering rows
is Phase 5. Ticket-side models are referenced by string to avoid import cycles.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

# Total delivery attempts allowed, including the first one.
MAX_DELIVERY_ATTEMPTS = 4


class NotificationEventType(models.TextChoices):
    TICKET_ROUTED = "TICKET_ROUTED", "Ticket created and routed"
    WORKER_ASSIGNED = "WORKER_ASSIGNED", "Worker assigned"
    DEPARTMENT_CHANGED = "DEPARTMENT_CHANGED", "Department changed"
    ASSESSMENT_SUBMITTED = "ASSESSMENT_SUBMITTED", "Assessment submitted"


class OutboxStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class NotificationOutbox(models.Model):
    ticket = models.ForeignKey("tickets.Ticket", on_delete=models.PROTECT, related_name="notification_outbox_rows")
    # The Activity entry that caused this notification.
    source_activity = models.ForeignKey(
        "tickets.TicketActivity", on_delete=models.PROTECT, related_name="notification_outbox_rows"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="notification_outbox_rows"
    )
    event_type = models.CharField(max_length=30, choices=NotificationEventType.choices)
    # Built from the source Activity and the recipient, so one event never notifies a person twice.
    idempotency_key = models.CharField(max_length=255, unique=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=OutboxStatus.choices, default=OutboxStatus.PENDING)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    # Lets the dispatcher recover rows left PROCESSING by a lost worker.
    processing_started_at = models.DateTimeField(null=True, blank=True)
    # When the row is next due: its creation time at first, a backoff time after a failed attempt.
    next_attempt_at = models.DateTimeField(default=timezone.now)
    # Last successful publish to the broker for the current attempt.
    last_dispatched_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "notification outbox"
        constraints = [
            models.CheckConstraint(
                condition=Q(attempt_count__gte=0, attempt_count__lte=MAX_DELIVERY_ATTEMPTS),
                name="outbox_attempt_count_in_range",
            ),
        ]
        indexes = [
            # The dispatcher's question: which PENDING rows are due now?
            models.Index(fields=["status", "next_attempt_at"], name="outbox_status_next_attempt"),
            # Operational inspection of one Ticket's notifications.
            models.Index(fields=["ticket", "created_at"], name="outbox_ticket_created"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} → {self.recipient.name} ({self.status})"

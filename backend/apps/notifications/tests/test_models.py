"""Database rules for NotificationOutbox (readmes/README-database-schema.md §2.18)."""

from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from apps.notifications.models import (
    MAX_DELIVERY_ATTEMPTS,
    NotificationEventType,
    NotificationOutbox,
    OutboxStatus,
)
from apps.tickets.tests.helpers import create_activity, create_ticket


class NotificationOutboxTests(TestCase):
    def setUp(self) -> None:
        self.ticket = create_ticket()
        self.activity = create_activity(self.ticket)

    def create_outbox_row(self, **fields) -> NotificationOutbox:
        fields.setdefault("recipient", self.ticket.created_by)
        fields.setdefault("idempotency_key", f"activity:{self.activity.pk}:recipient:{fields['recipient'].pk}")
        return NotificationOutbox.objects.create(
            ticket=self.ticket,
            source_activity=self.activity,
            event_type=NotificationEventType.TICKET_ROUTED,
            **fields,
        )

    def test_new_row_is_pending_with_no_attempts_and_is_due_immediately(self) -> None:
        row = self.create_outbox_row()

        self.assertEqual(row.status, OutboxStatus.PENDING)
        self.assertEqual(row.attempt_count, 0)
        self.assertEqual(row.payload, {})
        self.assertIsNotNone(row.next_attempt_at)
        self.assertIsNone(row.sent_at)

    def test_one_activity_cannot_notify_the_same_recipient_twice(self) -> None:
        self.create_outbox_row()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_outbox_row()

    def test_attempt_count_is_limited_to_the_documented_maximum(self) -> None:
        self.create_outbox_row(attempt_count=MAX_DELIVERY_ATTEMPTS)

        with self.assertRaises(IntegrityError), transaction.atomic():
            other_ticket = create_ticket()
            NotificationOutbox.objects.create(
                ticket=other_ticket,
                source_activity=create_activity(other_ticket),
                recipient=other_ticket.created_by,
                event_type=NotificationEventType.TICKET_ROUTED,
                idempotency_key="over-the-limit",
                attempt_count=MAX_DELIVERY_ATTEMPTS + 1,
            )

    def test_maximum_attempts_is_four(self) -> None:
        self.assertEqual(MAX_DELIVERY_ATTEMPTS, 4)

    def test_recipient_with_notifications_cannot_be_deleted(self) -> None:
        row = self.create_outbox_row()

        with self.assertRaises(ProtectedError):
            row.recipient.delete()

    def test_dispatcher_and_inspection_indexes_exist(self) -> None:
        with connection.cursor() as cursor:
            existing_names = set(connection.introspection.get_constraints(cursor, NotificationOutbox._meta.db_table))

        self.assertTrue({"outbox_status_next_attempt", "outbox_ticket_created"} <= existing_names)

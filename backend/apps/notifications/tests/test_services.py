from django.test import TestCase

from apps.accounts.models import UserRole
from apps.notifications.models import NotificationEventType, NotificationOutbox, OutboxStatus
from apps.notifications.services import create_notifications
from apps.organizations.tests.helpers import create_user
from apps.tickets.tests.helpers import create_activity, create_ticket


class CreateNotificationsTests(TestCase):
    def setUp(self) -> None:
        self.ticket = create_ticket()
        self.actor = create_user(UserRole.DEPARTMENT_POC)
        self.activity = create_activity(self.ticket, actor=self.actor)

    def create(self, recipients):
        return create_notifications(
            ticket=self.ticket,
            source_activity=self.activity,
            event_type=NotificationEventType.WORKER_ASSIGNED,
            recipients=recipients,
            actor=self.actor,
        )

    def test_each_distinct_recipient_gets_one_pending_row_with_a_stable_key(self) -> None:
        worker = create_user(UserRole.WORKER)

        rows = self.create([worker])

        self.assertEqual(len(rows), 1)
        row = NotificationOutbox.objects.get()
        self.assertEqual(row.recipient, worker)
        self.assertEqual(row.ticket, self.ticket)
        self.assertEqual(row.source_activity, self.activity)
        self.assertEqual(row.event_type, NotificationEventType.WORKER_ASSIGNED)
        self.assertEqual(row.status, OutboxStatus.PENDING)
        self.assertEqual(row.attempt_count, 0)
        self.assertEqual(row.idempotency_key, f"activity:{self.activity.id}:recipient:{worker.id}")
        self.assertEqual(row.payload, {"ticket_id": self.ticket.id, "ticket_number": self.ticket.ticket_number})

    def test_the_actor_is_never_notified_and_duplicate_recipients_collapse(self) -> None:
        manager = create_user(UserRole.FACILITY_MANAGER)

        self.create([manager, self.actor, manager])

        self.assertEqual(list(NotificationOutbox.objects.values_list("recipient_id", flat=True)), [manager.id])

    def test_no_recipients_creates_nothing(self) -> None:
        self.assertEqual(self.create([self.actor]), [])
        self.assertFalse(NotificationOutbox.objects.exists())

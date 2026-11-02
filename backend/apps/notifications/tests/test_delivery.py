"""The simulated delivery adapter (readmes/README-async-processing.md §1)."""

from django.test import TestCase

from apps.notifications.delivery import PermanentDeliveryError, deliver_simulated_notification
from apps.notifications.models import NotificationEventType
from apps.notifications.tests.helpers import create_outbox_row


class SimulatedDeliveryTests(TestCase):
    def test_delivery_logs_the_message_for_the_recipient(self) -> None:
        row = create_outbox_row(event_type=NotificationEventType.WORKER_ASSIGNED)

        with self.assertLogs("apps.notifications.delivery", level="INFO") as logs:
            deliver_simulated_notification(row)

        self.assertIn(f"recipient_id={row.recipient_id}", logs.output[0])
        self.assertIn(f"You were assigned to ticket {row.ticket.ticket_number}.", logs.output[0])

    def test_every_event_type_has_a_message(self) -> None:
        for event_type in NotificationEventType:
            with self.subTest(event_type=event_type):
                row = create_outbox_row(event_type=event_type)
                with self.assertLogs("apps.notifications.delivery", level="INFO"):
                    deliver_simulated_notification(row)

    def test_an_inactive_recipient_is_a_permanent_failure(self) -> None:
        row = create_outbox_row()
        row.recipient.is_active = False

        with self.assertRaises(PermanentDeliveryError):
            deliver_simulated_notification(row)

    def test_an_unknown_event_type_is_a_permanent_failure(self) -> None:
        row = create_outbox_row(event_type="SOMETHING_ELSE")

        with self.assertRaises(PermanentDeliveryError):
            deliver_simulated_notification(row)

    def test_a_payload_missing_the_ticket_number_is_a_permanent_failure(self) -> None:
        row = create_outbox_row(payload={})

        with self.assertRaises(PermanentDeliveryError):
            deliver_simulated_notification(row)

"""A Redis outage must not lose a notification or fail the ticket action.

Runs a real ticket action end to end (readmes/README-async-processing.md §6, §9).
"""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.notifications.dispatching import dispatch_due_notifications
from apps.notifications.models import NotificationOutbox, OutboxStatus
from apps.notifications.processing import process_notification
from apps.tickets.models import TicketAssignment
from apps.tickets.tests.helpers import create_scene

CELERY_APP = "apps.notifications.publishing.celery_app"


class BrokerOutageTests(APITestCase):
    def setUp(self) -> None:
        self.scene = create_scene()
        self.client.force_authenticate(self.scene.poc)

    def assign_worker(self):
        url = f"/api/v1/tickets/{self.scene.ticket.id}/assign-worker/"
        # execute=True runs the on-commit callbacks, as a real commit would.
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url, {"worker_id": self.scene.worker.id}, format="json")

    def test_assignment_succeeds_and_the_notification_is_recovered_after_the_outage(self) -> None:
        with patch(CELERY_APP) as celery_app, self.assertLogs("apps.notifications.publishing", level="ERROR"):
            celery_app.send_task.side_effect = ConnectionError("redis is down")
            response = self.assign_worker()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(TicketAssignment.objects.filter(worker=self.scene.worker, ended_at__isnull=True).exists())
        row = NotificationOutbox.objects.get(recipient=self.scene.worker)
        self.assertEqual((row.status, row.last_dispatched_at), (OutboxStatus.PENDING, None))

        with patch(CELERY_APP) as recovered_celery_app:
            result = dispatch_due_notifications()

        self.assertEqual(result.rows_published, 1)
        recovered_celery_app.send_task.assert_called_once()
        process_notification(row.id)
        row.refresh_from_db()
        self.assertEqual(row.status, OutboxStatus.SENT)

    def test_with_a_healthy_broker_the_commit_publishes_the_row_for_the_worker(self) -> None:
        with patch(CELERY_APP) as celery_app:
            response = self.assign_worker()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        row = NotificationOutbox.objects.get(recipient=self.scene.worker)
        celery_app.send_task.assert_called_once()
        self.assertEqual(celery_app.send_task.call_args.kwargs["args"], [row.id])
        row.refresh_from_db()
        self.assertIsNotNone(row.last_dispatched_at)

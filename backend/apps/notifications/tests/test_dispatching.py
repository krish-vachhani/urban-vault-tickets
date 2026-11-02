"""The dispatcher: which rows it publishes, and how it recovers lost work.

README-async-processing.md §9 and README-testing-strategy.md §5.1 "Dispatcher selection".
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.notifications import dispatching, tasks
from apps.notifications.constants import MAX_DELIVERY_ATTEMPTS, PROCESSING_LEASE
from apps.notifications.dispatching import ABANDONED_ATTEMPT_ERROR, dispatch_due_notifications
from apps.notifications.management.commands import dispatch_pending_notifications
from apps.notifications.models import NotificationOutbox, OutboxStatus
from apps.notifications.tests.helpers import create_outbox_row, create_stale_processing_row

CELERY_APP = "apps.notifications.publishing.celery_app"


class DispatchDueNotificationsTests(TestCase):
    def setUp(self) -> None:
        broker = patch(CELERY_APP)
        self.celery_app = broker.start()
        self.addCleanup(broker.stop)

    def published_ids(self) -> set[int]:
        return {call.kwargs["args"][0] for call in self.celery_app.send_task.call_args_list}

    def test_a_due_unpublished_row_is_published_and_marked(self) -> None:
        row = create_outbox_row()

        result = dispatch_due_notifications()

        self.assertEqual(self.published_ids(), {row.id})
        self.assertEqual((result.rows_published, result.stale_rows_recovered), (1, 0))
        row.refresh_from_db()
        self.assertIsNotNone(row.last_dispatched_at)

    def test_rows_that_are_not_due_or_not_pending_are_skipped(self) -> None:
        create_outbox_row(next_attempt_at=timezone.now() + timedelta(seconds=30))
        create_outbox_row(status=OutboxStatus.SENT, sent_at=timezone.now(), attempt_count=1)
        create_outbox_row(status=OutboxStatus.FAILED, attempt_count=MAX_DELIVERY_ATTEMPTS, last_error="x")
        create_outbox_row(status=OutboxStatus.PROCESSING, attempt_count=1, processing_started_at=timezone.now())

        result = dispatch_due_notifications()

        self.assertEqual(result.rows_published, 0)
        self.celery_app.send_task.assert_not_called()

    def test_a_row_is_not_republished_within_the_redispatch_interval(self) -> None:
        row = create_outbox_row()

        dispatch_due_notifications()
        dispatch_due_notifications()

        self.assertEqual(self.celery_app.send_task.call_count, 1)
        self.assertEqual(self.published_ids(), {row.id})

    def test_a_row_is_republished_once_the_redispatch_interval_has_passed(self) -> None:
        row = create_outbox_row(last_dispatched_at=timezone.now() - timedelta(seconds=301))

        dispatch_due_notifications()

        self.assertEqual(self.published_ids(), {row.id})

    @override_settings(NOTIFICATION_REDISPATCH_INTERVAL_SECONDS=10)
    def test_the_redispatch_interval_comes_from_settings(self) -> None:
        row = create_outbox_row(last_dispatched_at=timezone.now() - timedelta(seconds=11))

        dispatch_due_notifications()

        self.assertEqual(self.published_ids(), {row.id})

    def test_a_retry_is_published_only_after_it_becomes_due(self) -> None:
        row = create_outbox_row(attempt_count=1, next_attempt_at=timezone.now() + timedelta(seconds=30))
        dispatch_due_notifications()
        self.celery_app.send_task.assert_not_called()

        NotificationOutbox.objects.filter(id=row.id).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        dispatch_due_notifications()

        self.assertEqual(self.published_ids(), {row.id})

    def test_a_stale_processing_row_is_reset_and_published_again(self) -> None:
        row = create_stale_processing_row(attempt_count=2, last_dispatched_at=timezone.now())

        result = dispatch_due_notifications()

        self.assertEqual((result.stale_rows_recovered, result.rows_published), (1, 1))
        self.assertEqual(self.published_ids(), {row.id})
        row.refresh_from_db()
        self.assertEqual(row.status, OutboxStatus.PENDING)
        # The crashed attempt still counts against the limit.
        self.assertEqual(row.attempt_count, 2)
        self.assertEqual(row.last_error, ABANDONED_ATTEMPT_ERROR)
        self.assertIsNone(row.processing_started_at)

    def test_a_processing_row_within_its_lease_is_left_alone(self) -> None:
        started_at = timezone.now() - PROCESSING_LEASE + timedelta(minutes=1)
        row = create_outbox_row(status=OutboxStatus.PROCESSING, attempt_count=1, processing_started_at=started_at)

        result = dispatch_due_notifications()

        self.assertEqual((result.stale_rows_recovered, result.rows_published), (0, 0))
        row.refresh_from_db()
        self.assertEqual(row.status, OutboxStatus.PROCESSING)

    def test_a_stale_row_that_used_every_attempt_fails_instead_of_retrying(self) -> None:
        row = create_stale_processing_row(attempt_count=MAX_DELIVERY_ATTEMPTS)

        result = dispatch_due_notifications()

        self.assertEqual((result.stale_rows_recovered, result.rows_published), (1, 0))
        self.celery_app.send_task.assert_not_called()
        row.refresh_from_db()
        self.assertEqual(row.status, OutboxStatus.FAILED)
        self.assertEqual(row.last_error, ABANDONED_ATTEMPT_ERROR)

    def test_an_unreachable_broker_stops_the_run_and_leaves_the_rows_pending(self) -> None:
        rows = [create_outbox_row(), create_outbox_row()]
        self.celery_app.send_task.side_effect = ConnectionError("private-broker-details")

        with self.assertLogs("apps.notifications.publishing", level="ERROR") as logs:
            result = dispatch_due_notifications()

        self.assertTrue(all("private-broker-details" not in entry for entry in logs.output))
        self.assertTrue(all(record.exc_info is None for record in logs.records))
        self.assertEqual(result.rows_published, 0)
        self.assertEqual(self.celery_app.send_task.call_count, 1)
        for row in rows:
            row.refresh_from_db()
            self.assertEqual(row.status, OutboxStatus.PENDING)
            self.assertIsNone(row.last_dispatched_at)

    def test_one_run_publishes_at_most_one_batch(self) -> None:
        for _ in range(3):
            create_outbox_row()

        with patch.object(dispatching, "DISPATCH_BATCH_SIZE", 2):
            result = dispatch_due_notifications()

        self.assertEqual(result.rows_published, 2)


class DispatchEntryPointTests(TestCase):
    def test_the_manual_command_and_the_beat_task_run_the_same_dispatcher(self) -> None:
        self.assertIs(dispatch_pending_notifications.dispatch_due_notifications, dispatch_due_notifications)
        self.assertIs(tasks.dispatch_due_notifications, dispatch_due_notifications)

    def test_the_manual_command_publishes_due_rows_and_reports_the_counts(self) -> None:
        row = create_outbox_row()
        create_stale_processing_row()
        output = StringIO()

        with patch(CELERY_APP) as celery_app:
            call_command("dispatch_pending_notifications", stdout=output)

        self.assertIn("Recovered 1 stale notification(s); published 2 notification(s).", output.getvalue())
        self.assertIn(row.id, {call.kwargs["args"][0] for call in celery_app.send_task.call_args_list})

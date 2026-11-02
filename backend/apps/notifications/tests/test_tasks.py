"""The Celery tasks and the Beat schedule (README-async-processing.md §7, §9, §10)."""

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from apps.notifications import tasks
from apps.notifications.constants import (
    DELIVER_TASK_NAME,
    DELIVERY_TASK_TIME_LIMIT_SECONDS,
    DISPATCH_TASK_NAME,
    PROCESSING_LEASE,
)
from apps.notifications.models import OutboxStatus
from apps.notifications.tests.helpers import create_outbox_row
from config.celery import celery_app


class DeliverNotificationTaskTests(TestCase):
    def test_the_task_delivers_a_row_with_the_real_simulated_adapter(self) -> None:
        row = create_outbox_row()

        with self.assertLogs("apps.notifications.delivery", level="INFO"):
            tasks.deliver_notification.apply(args=[row.id]).get()

        row.refresh_from_db()
        self.assertEqual(row.status, OutboxStatus.SENT)
        self.assertIsNotNone(row.sent_at)

    def test_running_the_task_twice_sends_once(self) -> None:
        row = create_outbox_row()

        with self.assertLogs("apps.notifications.delivery", level="INFO") as delivery_logs:
            tasks.deliver_notification.apply(args=[row.id]).get()
            tasks.deliver_notification.apply(args=[row.id]).get()

        self.assertEqual(len(delivery_logs.output), 1)
        row.refresh_from_db()
        self.assertEqual(row.attempt_count, 1)


class CeleryConfigurationTests(SimpleTestCase):
    def test_both_tasks_are_registered_under_their_documented_names(self) -> None:
        self.assertIn(DELIVER_TASK_NAME, celery_app.tasks)
        self.assertIn(DISPATCH_TASK_NAME, celery_app.tasks)

    def test_the_delivery_task_has_a_hard_time_limit_far_below_the_processing_lease(self) -> None:
        self.assertEqual(tasks.deliver_notification.time_limit, DELIVERY_TASK_TIME_LIMIT_SECONDS)
        self.assertLess(DELIVERY_TASK_TIME_LIMIT_SECONDS * 2, PROCESSING_LEASE.total_seconds())

    def test_beat_runs_the_dispatcher_every_sixty_seconds(self) -> None:
        schedule = celery_app.conf.beat_schedule

        self.assertEqual(list(schedule.values()), [{"task": DISPATCH_TASK_NAME, "schedule": 60}])

    def test_results_are_not_stored(self) -> None:
        self.assertTrue(celery_app.conf.task_ignore_result)
        self.assertEqual(settings.NOTIFICATION_REDISPATCH_INTERVAL_SECONDS, 300)

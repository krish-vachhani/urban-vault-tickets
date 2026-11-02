"""One delivery attempt: success, retries, final failure, and harmless repeats.

The simulated delivery adapter is mocked so each test chooses its outcome; the task
function is called directly rather than through a broker.
README-async-processing.md §7, §8 and README-testing-strategy.md §5.1.
"""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.notifications.constants import BACKOFF_JITTER_RATIO, MAX_DELIVERY_ATTEMPTS, RETRY_BACKOFF_SECONDS
from apps.notifications.delivery import PermanentDeliveryError, TransientDeliveryError
from apps.notifications.models import NotificationOutbox, OutboxStatus
from apps.notifications.processing import calculate_next_attempt_at, process_notification
from apps.notifications.tests.helpers import create_outbox_row, create_stale_processing_row, make_due

DELIVER = "apps.notifications.processing.deliver_simulated_notification"


class ProcessNotificationTests(TestCase):
    def setUp(self) -> None:
        self.row = create_outbox_row()

    def process(self, **mock_options) -> None:
        with patch(DELIVER, **mock_options) as deliver:
            process_notification(self.row.id)
        self.deliver = deliver
        self.row.refresh_from_db()

    def test_successful_delivery_marks_the_row_sent(self) -> None:
        with self.assertLogs("apps.notifications.processing", level="INFO") as logs:
            self.process()

        self.deliver.assert_called_once()
        self.assertEqual(self.row.status, OutboxStatus.SENT)
        self.assertEqual(self.row.attempt_count, 1)
        self.assertIsNotNone(self.row.sent_at)
        self.assertIsNone(self.row.last_error)
        self.assertIsNone(self.row.processing_started_at)
        self.assertIn(f"notification_sent outbox_id={self.row.id}", logs.output[-1])

    def test_the_attempt_is_counted_and_marked_processing_before_delivery_starts(self) -> None:
        seen_during_delivery = {}

        def inspect_row(outbox: NotificationOutbox) -> None:
            seen_during_delivery["status"] = NotificationOutbox.objects.get(id=outbox.id).status
            seen_during_delivery["attempts"] = NotificationOutbox.objects.get(id=outbox.id).attempt_count

        self.process(side_effect=inspect_row)

        self.assertEqual(seen_during_delivery, {"status": OutboxStatus.PROCESSING, "attempts": 1})

    def test_transient_failure_schedules_a_retry(self) -> None:
        NotificationOutbox.objects.filter(id=self.row.id).update(last_dispatched_at=timezone.now())
        before = timezone.now()

        self.process(side_effect=TransientDeliveryError("provider timed out"))

        self.assertEqual(self.row.status, OutboxStatus.PENDING)
        self.assertEqual(self.row.attempt_count, 1)
        self.assertEqual(self.row.last_error, "TransientDeliveryError: provider timed out")
        # Cleared so the dispatcher publishes the row once the retry is due.
        self.assertIsNone(self.row.last_dispatched_at)
        self.assertIsNone(self.row.sent_at)
        first_delay = RETRY_BACKOFF_SECONDS[0]
        self.assertGreaterEqual(self.row.next_attempt_at, before + timedelta(seconds=first_delay))
        self.assertLessEqual(
            self.row.next_attempt_at, timezone.now() + timedelta(seconds=first_delay * (1 + BACKOFF_JITTER_RATIO))
        )

    def test_backoff_grows_with_each_attempt_and_stays_within_the_jitter_range(self) -> None:
        for attempts_used, base_delay in enumerate(RETRY_BACKOFF_SECONDS, start=1):
            with self.subTest(attempts_used=attempts_used):
                before = timezone.now()
                next_attempt_at = calculate_next_attempt_at(attempts_used)
                after = timezone.now()

                self.assertGreaterEqual(next_attempt_at, before + timedelta(seconds=base_delay))
                self.assertLessEqual(
                    next_attempt_at, after + timedelta(seconds=base_delay * (1 + BACKOFF_JITTER_RATIO))
                )

    def test_a_transient_failure_followed_by_success_ends_sent(self) -> None:
        self.process(side_effect=TransientDeliveryError("provider timed out"))
        make_due(self.row)

        self.process()

        self.assertEqual(self.row.status, OutboxStatus.SENT)
        self.assertEqual(self.row.attempt_count, 2)
        self.assertIsNone(self.row.last_error)

    def test_the_fourth_failed_attempt_is_final_and_keeps_the_error(self) -> None:
        for expected_attempt in range(1, MAX_DELIVERY_ATTEMPTS + 1):
            self.process(side_effect=TransientDeliveryError("provider timed out"))
            self.assertEqual(self.row.attempt_count, expected_attempt)
            make_due(self.row)

        self.assertEqual(self.row.status, OutboxStatus.FAILED)
        self.assertEqual(self.row.attempt_count, MAX_DELIVERY_ATTEMPTS)
        self.assertEqual(self.row.last_error, "TransientDeliveryError: provider timed out")
        self.assertIsNone(self.row.sent_at)

        self.process()

        self.deliver.assert_not_called()
        self.assertEqual(self.row.attempt_count, MAX_DELIVERY_ATTEMPTS)

    def test_a_permanent_failure_is_not_retried(self) -> None:
        self.process(side_effect=PermanentDeliveryError("The recipient account is inactive."))

        self.assertEqual(self.row.status, OutboxStatus.FAILED)
        self.assertEqual(self.row.attempt_count, 1)
        self.assertEqual(self.row.last_error, "PermanentDeliveryError: The recipient account is inactive.")

    def test_an_unexpected_error_is_retried_and_its_message_is_not_stored(self) -> None:
        with self.assertLogs("apps.notifications.processing", level="ERROR"):
            self.process(side_effect=RuntimeError("could not connect to redis://:s3cret@host"))

        self.assertEqual(self.row.status, OutboxStatus.PENDING)
        self.assertEqual(self.row.last_error, "RuntimeError: unexpected error during delivery.")
        self.assertNotIn("s3cret", self.row.last_error)

    def test_a_late_result_does_not_overwrite_a_state_set_meanwhile(self) -> None:
        def dispatcher_resets_the_row_during_delivery(outbox: NotificationOutbox) -> None:
            NotificationOutbox.objects.filter(id=outbox.id).update(status=OutboxStatus.PENDING)

        self.process(side_effect=dispatcher_resets_the_row_during_delivery)

        self.assertEqual(self.row.status, OutboxStatus.PENDING)
        self.assertIsNone(self.row.sent_at)


class DuplicateExecutionTests(TestCase):
    """Celery runs tasks at least once, so a repeated task must change nothing (§8)."""

    def assert_second_run_does_nothing(self, row: NotificationOutbox) -> None:
        before = NotificationOutbox.objects.values().get(id=row.id)

        with patch(DELIVER) as deliver:
            process_notification(row.id)

        deliver.assert_not_called()
        self.assertEqual(NotificationOutbox.objects.values().get(id=row.id), before)

    def test_running_the_task_again_after_sending_does_not_deliver_twice(self) -> None:
        row = create_outbox_row()
        with patch(DELIVER) as first_delivery:
            process_notification(row.id)
        first_delivery.assert_called_once()

        self.assert_second_run_does_nothing(row)

        row.refresh_from_db()
        self.assertEqual((row.status, row.attempt_count), (OutboxStatus.SENT, 1))

    def test_a_finally_failed_row_is_left_alone(self) -> None:
        self.assert_second_run_does_nothing(
            create_outbox_row(status=OutboxStatus.FAILED, attempt_count=MAX_DELIVERY_ATTEMPTS, last_error="x")
        )

    def test_a_row_another_worker_is_processing_is_left_alone(self) -> None:
        self.assert_second_run_does_nothing(
            create_outbox_row(status=OutboxStatus.PROCESSING, attempt_count=1, processing_started_at=timezone.now())
        )

    def test_a_message_that_arrives_before_the_retry_is_due_is_left_alone(self) -> None:
        self.assert_second_run_does_nothing(
            create_outbox_row(attempt_count=1, next_attempt_at=timezone.now() + timedelta(seconds=30))
        )

    def test_an_abandoned_row_is_left_to_the_dispatcher(self) -> None:
        # Claiming it here could push attempt_count past the limit; the dispatcher resets it safely.
        self.assert_second_run_does_nothing(create_stale_processing_row(attempt_count=MAX_DELIVERY_ATTEMPTS))

    def test_an_unknown_outbox_id_is_ignored(self) -> None:
        with self.assertLogs("apps.notifications.processing", level="WARNING"):
            process_notification(999_999)

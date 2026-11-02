"""Celery tasks. They only pass control to the notification code; the logic lives elsewhere."""

from celery import shared_task

from apps.notifications.constants import DELIVER_TASK_NAME, DELIVERY_TASK_TIME_LIMIT_SECONDS, DISPATCH_TASK_NAME
from apps.notifications.dispatching import dispatch_due_notifications
from apps.notifications.processing import process_notification


@shared_task(name=DELIVER_TASK_NAME, time_limit=DELIVERY_TASK_TIME_LIMIT_SECONDS)
def deliver_notification(outbox_id: int) -> None:
    """Make one delivery attempt for an outbox row. Safe to run more than once for the same row."""
    process_notification(outbox_id)


@shared_task(name=DISPATCH_TASK_NAME)
def dispatch_notifications() -> None:
    """Run by Celery Beat every minute: publish due rows and recover abandoned ones."""
    dispatch_due_notifications()

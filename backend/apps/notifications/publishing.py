"""Publishes an outbox row ID to the Celery broker.

Used both right after a ticket action commits and by the periodic dispatcher. The task is
sent by name so this module never imports the task module, which keeps the imports acyclic.
"""

import logging

from django.utils import timezone

from apps.notifications.constants import DELIVER_TASK_NAME
from apps.notifications.models import NotificationOutbox, OutboxStatus
from config.celery import celery_app

logger = logging.getLogger(__name__)


def publish_notification(outbox_id: int) -> bool:
    """Send the delivery task to Redis. Return False, leaving the row PENDING, if the broker refuses it.

    Never raises: a Redis outage must not turn an already-committed ticket action into an API
    error. The dispatcher publishes the row later (README-async-processing.md §6).
    """
    try:
        celery_app.send_task(DELIVER_TASK_NAME, args=[outbox_id])
    except Exception as error:  # Kombu and Redis raise many unrelated error types
        # Broker exceptions may include credentials; keep only the type and our own identifiers.
        logger.error("notification_publish_failed outbox_id=%s error_type=%s", outbox_id, type(error).__name__)
        return False

    _record_publish(outbox_id)
    return True


def _record_publish(outbox_id: int) -> None:
    """Remember the publish so the dispatcher does not repeat it on every tick.

    This is a conditional UPDATE, not a save(): by now a fast worker may already have moved the
    row on, and that newer state must not be overwritten. A row waiting for a future retry
    is skipped, because its next publish belongs to a later attempt.
    """
    now = timezone.now()
    NotificationOutbox.objects.filter(id=outbox_id, status=OutboxStatus.PENDING, next_attempt_at__lte=now).update(
        last_dispatched_at=now
    )

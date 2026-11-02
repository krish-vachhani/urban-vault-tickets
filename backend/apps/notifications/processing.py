"""Runs one delivery attempt for an outbox row: claim it, deliver, then record the outcome.

Rules: readmes/README-async-processing.md §7 and §8. Celery may run a task more than once,
so every early return below is what makes a repeated or concurrent run harmless.
The task never calls Celery's retry(): a failed attempt is rescheduled in PostgreSQL through
next_attempt_at and published again by the dispatcher.
"""

import logging
import random
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.notifications.constants import (
    BACKOFF_JITTER_RATIO,
    MAX_DELIVERY_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
)
from apps.notifications.delivery import DeliveryError, PermanentDeliveryError, deliver_simulated_notification
from apps.notifications.models import NotificationOutbox, OutboxStatus

logger = logging.getLogger(__name__)

MAX_ERROR_MESSAGE_LENGTH = 500


def process_notification(outbox_id: int) -> None:
    """Make at most one delivery attempt for the row. Does nothing if the row should not be attempted now."""
    outbox = _claim_for_delivery(outbox_id)
    if outbox is None:
        return

    # Delivery runs outside any transaction, so the PROCESSING claim is already visible to other workers.
    try:
        deliver_simulated_notification(outbox)
    except PermanentDeliveryError as error:
        _record_failure(outbox, error, can_retry=False)
    except Exception as error:  # a transient error, or an unexpected one that must not leave the row PROCESSING
        if not isinstance(error, DeliveryError):
            # Arbitrary exception text can contain provider credentials or connection strings.
            logger.error("notification_unexpected_error %s error_type=%s", _describe(outbox), type(error).__name__)
        _record_failure(outbox, error, can_retry=True)
    else:
        _record_success(outbox)


def calculate_next_attempt_at(attempts_used: int) -> datetime:
    """Return when the next attempt is due: the backoff step for this attempt plus up to 20% random jitter."""
    base_delay_seconds = RETRY_BACKOFF_SECONDS[attempts_used - 1]
    jitter_seconds = random.uniform(0, base_delay_seconds * BACKOFF_JITTER_RATIO)
    return timezone.now() + timedelta(seconds=base_delay_seconds + jitter_seconds)


def _claim_for_delivery(outbox_id: int) -> NotificationOutbox | None:
    """Lock the row, mark it PROCESSING for a new attempt, and commit. Return None if it must not be attempted."""
    with transaction.atomic():
        outbox = (
            NotificationOutbox.objects.select_for_update(of=("self",))
            .select_related("recipient")
            .filter(id=outbox_id)
            .first()
        )
        if outbox is None:
            logger.warning("notification_missing outbox_id=%s", outbox_id)
            return None
        if outbox.status in (OutboxStatus.SENT, OutboxStatus.FAILED):
            logger.info("notification_already_finished %s", _describe(outbox))
            return None
        if outbox.status == OutboxStatus.PROCESSING:
            # Another worker is delivering it. If that worker died, the dispatcher resets the row
            # once its lease expires; claiming here could exceed the attempt limit.
            logger.info("notification_already_processing %s", _describe(outbox))
            return None
        if outbox.next_attempt_at > timezone.now():
            logger.info("notification_not_due_yet %s", _describe(outbox))
            return None

        outbox.attempt_count += 1
        outbox.status = OutboxStatus.PROCESSING
        outbox.processing_started_at = timezone.now()
        outbox.save(update_fields=["attempt_count", "status", "processing_started_at", "updated_at"])
    return outbox


def _record_success(outbox: NotificationOutbox) -> None:
    now = timezone.now()
    if _finish_attempt(outbox, status=OutboxStatus.SENT, sent_at=now, last_error=None):
        logger.info("notification_sent %s", _describe(outbox))


def _record_failure(outbox: NotificationOutbox, error: Exception, *, can_retry: bool) -> None:
    last_error = _summarize_error(error)
    if can_retry and outbox.attempt_count < MAX_DELIVERY_ATTEMPTS:
        retry_recorded = _finish_attempt(
            outbox,
            status=OutboxStatus.PENDING,
            next_attempt_at=calculate_next_attempt_at(outbox.attempt_count),
            # Cleared so the dispatcher publishes the row once the retry is due.
            last_dispatched_at=None,
            last_error=last_error,
        )
        if retry_recorded:
            logger.warning("notification_retry_scheduled %s error=%r", _describe(outbox), last_error)
    elif _finish_attempt(outbox, status=OutboxStatus.FAILED, last_error=last_error):
        logger.error("notification_failed %s error=%r", _describe(outbox), last_error)


def _finish_attempt(outbox: NotificationOutbox, **changes: object) -> bool:
    """Apply the attempt's outcome only if the row is still the PROCESSING claim this run made.

    A conditional UPDATE keeps a late finish from overwriting a state the dispatcher set meanwhile.
    """
    updated_rows = NotificationOutbox.objects.filter(
        id=outbox.id, status=OutboxStatus.PROCESSING, attempt_count=outbox.attempt_count
    ).update(processing_started_at=None, updated_at=timezone.now(), **changes)
    if updated_rows == 0:
        logger.warning("notification_attempt_superseded %s", _describe(outbox))
    return updated_rows == 1


def _summarize_error(error: Exception) -> str:
    """Return a short error text that is safe to store.

    Delivery errors are written by this app, so their message is kept. Anything else could
    carry connection strings or tokens, so only its class name is stored.
    """
    if isinstance(error, DeliveryError):
        return f"{type(error).__name__}: {str(error)[:MAX_ERROR_MESSAGE_LENGTH]}"
    return f"{type(error).__name__}: unexpected error during delivery."


def _describe(outbox: NotificationOutbox) -> str:
    return (
        f"outbox_id={outbox.id} ticket_id={outbox.ticket_id} event_type={outbox.event_type} "
        f"recipient_id={outbox.recipient_id} attempt={outbox.attempt_count}"
    )

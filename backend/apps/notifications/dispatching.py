"""Finds outbox rows that need publishing and recovers work abandoned by a lost worker.

The periodic Celery Beat task and the dispatch_pending_notifications management command
both call dispatch_due_notifications(), so scheduled and manual recovery cannot drift apart.
Reference: readmes/README-async-processing.md §9.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.notifications.constants import DISPATCH_BATCH_SIZE, MAX_DELIVERY_ATTEMPTS, PROCESSING_LEASE
from apps.notifications.models import NotificationOutbox, OutboxStatus
from apps.notifications.publishing import publish_notification

logger = logging.getLogger(__name__)

ABANDONED_ATTEMPT_ERROR = "The worker stopped before the delivery attempt finished."


@dataclass(frozen=True)
class DispatchResult:
    stale_rows_recovered: int
    rows_published: int


def dispatch_due_notifications() -> DispatchResult:
    """Recover abandoned PROCESSING rows, then publish every PENDING row that is due and not yet published."""
    stale_rows_recovered = recover_stale_processing_rows()
    rows_published = publish_due_rows()
    logger.info(
        "notification_dispatch_finished stale_rows_recovered=%s rows_published=%s",
        stale_rows_recovered,
        rows_published,
    )
    return DispatchResult(stale_rows_recovered=stale_rows_recovered, rows_published=rows_published)


def recover_stale_processing_rows() -> int:
    """Reset rows whose processing lease expired. A crashed attempt still counts, so an exhausted row fails."""
    now = timezone.now()
    with transaction.atomic():
        stale_rows = list(
            NotificationOutbox.objects.select_for_update(skip_locked=True).filter(
                status=OutboxStatus.PROCESSING, processing_started_at__lte=now - PROCESSING_LEASE
            )
        )
        for row in stale_rows:
            if row.attempt_count >= MAX_DELIVERY_ATTEMPTS:
                row.status = OutboxStatus.FAILED
            else:
                row.status = OutboxStatus.PENDING
                row.next_attempt_at = now
                row.last_dispatched_at = None
            row.processing_started_at = None
            row.last_error = ABANDONED_ATTEMPT_ERROR
            row.save(
                update_fields=[
                    "status",
                    "next_attempt_at",
                    "last_dispatched_at",
                    "processing_started_at",
                    "last_error",
                    "updated_at",
                ]
            )
            logger.warning(
                "notification_stale_recovered outbox_id=%s attempt=%s new_status=%s",
                row.id,
                row.attempt_count,
                row.status,
            )
    return len(stale_rows)


def publish_due_rows() -> int:
    """Publish due PENDING rows that were never published for this attempt, or whose message was probably lost."""
    now = timezone.now()
    republish_before = now - timedelta(seconds=settings.NOTIFICATION_REDISPATCH_INTERVAL_SECONDS)
    never_or_long_ago_published = Q(last_dispatched_at__isnull=True) | Q(last_dispatched_at__lte=republish_before)

    published_count = 0
    # skip_locked lets overlapping runs (Beat plus the manual command) take different rows instead of the same ones.
    with transaction.atomic():
        due_rows = (
            NotificationOutbox.objects.select_for_update(skip_locked=True)
            .filter(never_or_long_ago_published, status=OutboxStatus.PENDING, next_attempt_at__lte=now)
            .order_by("next_attempt_at")[:DISPATCH_BATCH_SIZE]
        )
        for row in due_rows:
            if not publish_notification(row.id):
                # The broker is unreachable; the remaining rows stay PENDING for the next run.
                break
            published_count += 1
    return published_count

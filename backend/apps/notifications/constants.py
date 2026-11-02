"""Delivery, retry, and recovery limits for notifications, kept in one place.

Reference: readmes/README-async-processing.md §7 and §9.
This module imports nothing from Django so that settings.py can read it.
"""

from datetime import timedelta

# Total delivery attempts allowed, including the first one.
MAX_DELIVERY_ATTEMPTS = 4

# Seconds to wait before the 2nd, 3rd, and 4th attempt. The wait after attempt N is entry N - 1.
RETRY_BACKOFF_SECONDS = (30, 60, 120)
# Each wait gets up to this share added at random, so retries do not all land at the same moment.
BACKOFF_JITTER_RATIO = 0.2

# A PROCESSING row older than this is treated as abandoned by a lost worker.
PROCESSING_LEASE = timedelta(minutes=5)
# Must stay well below PROCESSING_LEASE so a slow but valid delivery is never mistaken for abandoned work.
DELIVERY_TASK_TIME_LIMIT_SECONDS = 60

# How often Celery Beat runs the dispatcher.
DISPATCH_SCHEDULE_SECONDS = 60
# How long a published-but-unprocessed row waits before it is published again (default; overridable by env).
DEFAULT_REDISPATCH_INTERVAL_SECONDS = 300
# Most rows one dispatcher run publishes, so a long backlog never holds row locks for long.
DISPATCH_BATCH_SIZE = 100

# Explicit Celery task names, so the publisher and Beat can refer to a task without importing it.
DELIVER_TASK_NAME = "notifications.deliver_notification"
DISPATCH_TASK_NAME = "notifications.dispatch_notifications"

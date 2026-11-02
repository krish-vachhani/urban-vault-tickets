"""Manual recovery: publish due notifications and recover abandoned ones.

Runs the same logic as the periodic Celery Beat task (readmes/README-async-processing.md §9).
"""

from django.core.management.base import BaseCommand

from apps.notifications.dispatching import dispatch_due_notifications


class Command(BaseCommand):
    help = "Publish due PENDING notifications to Celery and reset PROCESSING rows abandoned by a lost worker."

    def handle(self, *args, **options) -> None:
        result = dispatch_due_notifications()
        self.stdout.write(
            f"Recovered {result.stale_rows_recovered} stale notification(s); "
            f"published {result.rows_published} notification(s)."
        )

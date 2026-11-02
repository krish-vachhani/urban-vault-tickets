from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Transactional outbox and Celery delivery of simulated ticket notifications."""

    name = "apps.notifications"
    # Short label keeps model references stable, e.g. "notifications.ModelName".
    label = "notifications"
    verbose_name = "Notifications"

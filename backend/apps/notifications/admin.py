"""Django admin for inspecting notification outbox rows. Not part of the product UI."""

from django.contrib import admin

from apps.notifications.models import NotificationOutbox


@admin.register(NotificationOutbox)
class NotificationOutboxAdmin(admin.ModelAdmin):
    list_display = ["ticket", "recipient", "event_type", "status", "attempt_count", "next_attempt_at"]
    list_filter = ["status", "event_type"]
    list_select_related = ["ticket", "recipient"]

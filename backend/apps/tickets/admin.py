"""Django admin for inspecting tickets and their history. Not part of the product UI."""

from django.contrib import admin

from apps.tickets.models import (
    Ticket,
    TicketActivity,
    TicketAssessment,
    TicketAssignment,
    TicketComment,
    TicketFloor,
    TicketIssue,
)


class TicketIssueInline(admin.TabularInline):
    model = TicketIssue
    extra = 0


class TicketFloorInline(admin.TabularInline):
    model = TicketFloor
    extra = 0


class TicketAssignmentInline(admin.TabularInline):
    model = TicketAssignment
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        "ticket_number",
        "client_office",
        "current_department",
        "workflow_stage",
        "status",
        "created_by",
        "created_at",
    ]
    list_filter = ["status", "workflow_stage", "current_department", "client_office__client"]
    search_fields = ["id", "ticket_issues__issue__name"]
    ordering = ["-created_at"]
    list_select_related = ["client_office", "current_department", "created_by"]
    inlines = [TicketIssueInline, TicketFloorInline, TicketAssignmentInline]


@admin.register(TicketAssessment)
class TicketAssessmentAdmin(admin.ModelAdmin):
    list_display = ["ticket", "outcome", "submitted_by", "submitted_at"]
    list_filter = ["outcome"]
    list_select_related = ["ticket", "submitted_by"]


@admin.register(TicketActivity)
class TicketActivityAdmin(admin.ModelAdmin):
    """Read-only: Activity entries are append-only audit records."""

    list_display = ["ticket", "event_type", "actor", "created_at"]
    list_filter = ["event_type"]
    list_select_related = ["ticket", "actor"]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ["ticket", "author", "created_at"]
    search_fields = ["body"]
    list_select_related = ["ticket", "author"]

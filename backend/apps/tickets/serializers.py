"""Request validation and response shapes for the Ticket API.

Shapes: readmes/README-ticket-creation-api.md, README-ticket-listing-api.md,
README-ticket-actions-api.md, README-api-conventions.md §6. Serializers check the shape of
a request; the rules that need the database or the Ticket's state live in services.py.
"""

from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from apps.accounts.models import User, UserRole
from apps.organizations.role_labels import get_name_with_role_label, get_role_label
from apps.organizations.serializers import IdNameSerializer
from apps.tickets import selectors
from apps.tickets.models import (
    AssessmentOutcome,
    Ticket,
    TicketActivity,
    TicketAssignment,
    TicketComment,
    WorkflowStage,
)
from apps.tickets.permissions import get_available_actions, is_action_required

# Upper bound for free text (Description, forwarding note, comment body).
TEXT_MAX_LENGTH = 5000
ISSUE_SEARCH_MAX_LENGTH = 255

WORKER_ASSIGNED_MESSAGE = "Worker assigned successfully."


# --- Requests ------------------------------------------------------------------------------------------


def _reject_duplicate_ids(ids: list[int]) -> list[int]:
    if len(set(ids)) != len(ids):
        raise serializers.ValidationError("Duplicate IDs are not allowed.")
    return ids


class TicketCreateSerializer(serializers.Serializer):
    """Only these fields are read; creator, Departments, stage, and status are always server-derived."""

    client_office_id = serializers.IntegerField(min_value=1)
    issue_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)
    floor_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list)
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default=None, max_length=TEXT_MAX_LENGTH
    )

    def validate_issue_ids(self, issue_ids: list[int]) -> list[int]:
        return _reject_duplicate_ids(issue_ids)

    def validate_floor_ids(self, floor_ids: list[int]) -> list[int]:
        return _reject_duplicate_ids(floor_ids)

    def validate_description(self, description: str | None) -> str | None:
        return description or None

    def validate(self, attributes: dict[str, Any]) -> dict[str, Any]:
        creator: User = self.context["request"].user
        # Clients may omit the description; internal employees must explain the issue.
        if creator.role != UserRole.CLIENT and attributes["description"] is None:
            raise serializers.ValidationError({"description": ["This field is required."]})
        return attributes


class TicketListQuerySerializer(serializers.Serializer):
    """Query parameters of GET /tickets/. Page and page_size are validated by the paginator."""

    tab = serializers.ChoiceField(choices=[selectors.TAB_OPEN, selectors.TAB_CLOSED], default=selectors.TAB_OPEN)
    search = serializers.CharField(required=False, allow_blank=True, default="", max_length=ISSUE_SEARCH_MAX_LENGTH)
    client_id = serializers.IntegerField(min_value=1, required=False)
    department_id = serializers.IntegerField(min_value=1, required=False)
    facility_manager_id = serializers.IntegerField(min_value=1, required=False)
    workflow_stage = serializers.ChoiceField(choices=WorkflowStage.choices, required=False)
    ordering = serializers.ChoiceField(
        choices=[selectors.ORDER_NEWEST_FIRST, selectors.ORDER_OLDEST_FIRST], default=selectors.ORDER_NEWEST_FIRST
    )


class ActivityQuerySerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=[selectors.FEED_TYPE_ALL, selectors.FEED_TYPE_ACTIONS, selectors.FEED_TYPE_COMMENTS],
        default=selectors.FEED_TYPE_ALL,
    )


class AssignWorkerSerializer(serializers.Serializer):
    worker_id = serializers.IntegerField(min_value=1)


class ChangeDepartmentSerializer(serializers.Serializer):
    department_id = serializers.IntegerField(min_value=1)
    forwarding_note = serializers.CharField(max_length=TEXT_MAX_LENGTH)


class SubmitAssessmentSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=AssessmentOutcome.choices)


class AddCommentSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=TEXT_MAX_LENGTH)


# --- Shared response pieces ----------------------------------------------------------------------------


class UserSummarySerializer(serializers.Serializer):
    """A person as shown on a Ticket: never an email address or other profile field."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    role = serializers.CharField()
    role_label = serializers.SerializerMethodField()

    def get_role_label(self, user: User) -> str:
        return get_role_label(user)


class AssessmentSerializer(serializers.Serializer):
    outcome = serializers.CharField()
    submitted_by = UserSummarySerializer()
    submitted_at = serializers.DateTimeField()


# --- Ticket list and detail ----------------------------------------------------------------------------


class TicketListSerializer(serializers.Serializer):
    """A Ticket card. Expects a Ticket loaded through selectors.get_ticket_list or the detail queryset."""

    id = serializers.IntegerField()
    ticket_number = serializers.CharField()
    client = IdNameSerializer(source="client_office.client")
    client_office = IdNameSerializer()
    issues = IdNameSerializer(many=True)
    floors = IdNameSerializer(many=True)
    workflow_stage = serializers.CharField()
    status = serializers.CharField()
    created_by = UserSummarySerializer()
    created_at = serializers.DateTimeField()
    current_department = IdNameSerializer()
    current_assignees = serializers.SerializerMethodField()
    action_required = serializers.SerializerMethodField()

    def get_current_assignees(self, ticket: Ticket) -> list[dict[str, Any]]:
        """The Department POC, then the active Worker if there is one (otherwise the Ticket is Unassigned)."""
        assignees = [ticket.current_department.poc_user]
        active_assignment = selectors.get_prefetched_active_assignment(ticket)
        if active_assignment is not None:
            assignees.append(active_assignment.worker)
        return UserSummarySerializer(assignees, many=True).data

    def get_action_required(self, ticket: Ticket) -> bool:
        user: User = self.context["request"].user
        return is_action_required(user, ticket, selectors.get_prefetched_active_assignment(ticket))


class TicketDetailSerializer(TicketListSerializer):
    description = serializers.CharField(allow_null=True)
    origin_department = IdNameSerializer()
    closed_by = UserSummarySerializer(allow_null=True)
    closed_at = serializers.DateTimeField(allow_null=True)
    current_poc = serializers.SerializerMethodField()
    current_worker = serializers.SerializerMethodField()
    assessment = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()

    def get_current_poc(self, ticket: Ticket) -> dict[str, Any]:
        return UserSummarySerializer(ticket.current_department.poc_user).data

    def get_current_worker(self, ticket: Ticket) -> dict[str, Any] | None:
        active_assignment = selectors.get_prefetched_active_assignment(ticket)
        return UserSummarySerializer(active_assignment.worker).data if active_assignment else None

    def get_assessment(self, ticket: Ticket) -> dict[str, Any] | None:
        try:
            return AssessmentSerializer(ticket.assessment).data
        except ObjectDoesNotExist:
            return None

    def get_available_actions(self, ticket: Ticket) -> dict[str, bool]:
        user: User = self.context["request"].user
        return get_available_actions(user, ticket, selectors.get_prefetched_active_assignment(ticket))


class FilterOptionsSerializer(serializers.Serializer):
    clients = IdNameSerializer(many=True)
    departments = IdNameSerializer(many=True)
    facility_managers = IdNameSerializer(many=True)
    workflow_stages = serializers.SerializerMethodField()

    def get_workflow_stages(self, options: dict) -> list[dict[str, str]]:
        return [{"value": value, "label": label} for value, label in WorkflowStage.choices]


# --- Action results ------------------------------------------------------------------------------------


class AssignWorkerResponseSerializer(serializers.Serializer):
    """Built from the new TicketAssignment."""

    message = serializers.SerializerMethodField()
    ticket_id = serializers.IntegerField()
    workflow_stage = serializers.CharField(source="ticket.workflow_stage")
    worker = UserSummarySerializer()

    def get_message(self, assignment: TicketAssignment) -> str:
        return WORKER_ASSIGNED_MESSAGE


class ChangeDepartmentResponseSerializer(serializers.Serializer):
    """Built from the updated Ticket."""

    ticket_id = serializers.IntegerField(source="id")
    current_department = IdNameSerializer()
    workflow_stage = serializers.CharField()
    status = serializers.CharField()


class SubmitAssessmentResponseSerializer(serializers.Serializer):
    """Built from the new TicketAssessment."""

    ticket_id = serializers.IntegerField()
    outcome = serializers.CharField()
    workflow_stage = serializers.CharField(source="ticket.workflow_stage")
    status = serializers.CharField(source="ticket.status")


class MarkResolvedResponseSerializer(serializers.Serializer):
    """Built from the closed Ticket."""

    ticket_id = serializers.IntegerField(source="id")
    workflow_stage = serializers.CharField()
    status = serializers.CharField()
    closed_by = UserSummarySerializer()
    closed_at = serializers.DateTimeField()


# --- Activity feed and History -------------------------------------------------------------------------


class ActivityItemSerializer(serializers.Serializer):
    """One feed row (an action or a comment). Expects context["actors"], a user-ID → User map."""

    id = serializers.SerializerMethodField()
    type = serializers.CharField(source="item_type")
    event_type = serializers.CharField(source="item_event_type", allow_null=True)
    actor = serializers.SerializerMethodField()
    description = serializers.CharField(source="item_text")
    change = serializers.SerializerMethodField()
    note = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source="occurred_at")

    def get_id(self, row: dict[str, Any]) -> str:
        # Action and comment IDs come from different tables, so the prefix keeps them unique.
        return f"{row['item_type'].lower()}-{row['item_id']}"

    def get_actor(self, row: dict[str, Any]) -> dict[str, Any] | None:
        actor = self.context["actors"].get(row["item_actor_id"])
        return UserSummarySerializer(actor).data if actor else None

    def get_change(self, row: dict[str, Any]) -> dict[str, str] | None:
        return (row["item_metadata"] or {}).get("change")

    def get_note(self, row: dict[str, Any]) -> str | None:
        return (row["item_metadata"] or {}).get("note")


def build_feed_row_for_comment(comment: TicketComment) -> dict[str, Any]:
    """A new comment in the same shape as a feed row, so POST /comments/ and the feed agree."""
    return {
        "item_id": comment.id,
        "item_type": selectors.FEED_ITEM_COMMENT,
        "item_event_type": None,
        "item_actor_id": comment.author_id,
        "item_text": comment.body,
        "item_metadata": None,
        "occurred_at": comment.created_at,
    }


class AssignmentHistorySerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    actor = UserSummarySerializer(source="assigned_by")
    worker = UserSummarySerializer()
    change = serializers.SerializerMethodField()
    assigned_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    end_reason = serializers.CharField(allow_null=True)

    def get_id(self, assignment: TicketAssignment) -> str:
        return f"assignment-{assignment.id}"

    def get_type(self, assignment: TicketAssignment) -> str:
        return "ASSIGNMENT"

    def get_change(self, assignment: TicketAssignment) -> dict[str, str]:
        # previous_assignee is set by selectors.get_ticket_history; it is "Unassigned" for the first assignment.
        return {
            "field": "assignee",
            "from": assignment.previous_assignee,
            "to": get_name_with_role_label(assignment.worker),
        }


class DepartmentChangeHistorySerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    actor = UserSummarySerializer()
    change = serializers.SerializerMethodField()
    note = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    def get_id(self, activity: TicketActivity) -> str:
        return f"department-change-{activity.id}"

    def get_type(self, activity: TicketActivity) -> str:
        return "DEPARTMENT_CHANGE"

    def get_change(self, activity: TicketActivity) -> dict[str, str] | None:
        return activity.metadata.get("change")

    def get_note(self, activity: TicketActivity) -> str | None:
        return activity.metadata.get("note")


class TicketHistorySerializer(serializers.Serializer):
    assignments = AssignmentHistorySerializer(many=True)
    department_changes = DepartmentChangeHistorySerializer(many=True)

"""Ticket business operations. Each one owns its transaction and writes its Activity and outbox rows.

Rules: readmes/README-ticket-lifecycle.md, README-ticket-creation-api.md, README-ticket-actions-api.md.

State-changing services take a Ticket ID, not an object. They lock the row with a separate
primary-key query, then re-check visibility, permission, and state against the locked row, so
two racing requests cannot both pass a check made before the lock.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.generics import get_object_or_404

from apps.accounts.models import User
from apps.notifications.models import NotificationEventType
from apps.notifications.services import create_notifications
from apps.organizations.models import ClientOffice, Department, Floor, Issue
from apps.organizations.role_labels import get_name_with_role_label
from apps.organizations.selectors import get_authorized_offices, get_office_floors
from apps.tickets import selectors
from apps.tickets.activity import build_change, record_activity
from apps.tickets.exceptions import InvalidTicketTransition
from apps.tickets.models import (
    ActivityEventType,
    AssessmentOutcome,
    AssignmentEndReason,
    Ticket,
    TicketAssessment,
    TicketAssignment,
    TicketComment,
    TicketFloor,
    TicketIssue,
    TicketStatus,
    WorkflowStage,
)
from apps.tickets.permissions import (
    NOT_ALLOWED_TO_RESOLVE_MESSAGE,
    NOT_ASSIGNED_WORKER_MESSAGE,
    NOT_CURRENT_POC_MESSAGE,
    can_mark_resolved,
    is_assigned_worker,
    is_current_department_poc,
)

# One message for "does not exist" and "not yours", so a response never reveals other Clients' records.
INVALID_OFFICE_MESSAGE = "Select a valid client office."
INVALID_ISSUES_MESSAGE = "Select valid issues."
INVALID_FLOORS_MESSAGE = "Select valid floors for this office."
INVALID_WORKER_MESSAGE = "Select a valid worker."
INVALID_DEPARTMENT_MESSAGE = "Select a valid department."
SAME_DEPARTMENT_MESSAGE = "The ticket is already in this department."


# --- Ticket creation ---------------------------------------------------------------------------------


def create_ticket(
    *, creator: User, client_office_id: int, issue_ids: list[int], floor_ids: list[int], description: str | None
) -> Ticket:
    """Validate against the database, then write the Ticket, its Issues and Floors, Activity, and outbox rows together."""
    office = _get_creatable_office(creator, client_office_id)
    issues = _get_issues(issue_ids)
    department = _get_common_department(issues)
    floors = _get_affected_floors(office, floor_ids)

    with transaction.atomic():
        ticket = Ticket.objects.create(
            client_office=office,
            created_by=creator,
            origin_department=department,
            current_department=department,
            description=description,
        )
        TicketIssue.objects.bulk_create(TicketIssue(ticket=ticket, issue=issue) for issue in issues)
        TicketFloor.objects.bulk_create(TicketFloor(ticket=ticket, floor=floor) for floor in floors)

        record_activity(ticket, creator, ActivityEventType.TICKET_CREATED, "created the ticket.")
        routing_activity = record_activity(
            ticket,
            None,
            ActivityEventType.TICKET_ROUTED,
            f"Ticket routed to the {department.name} department.",
            metadata={
                "department_id": department.id,
                "change": build_change("assignee", "Unassigned", get_name_with_role_label(department.poc_user)),
            },
        )
        create_notifications(
            ticket=ticket,
            source_activity=routing_activity,
            event_type=NotificationEventType.TICKET_ROUTED,
            recipients=[office.property.facility_manager, department.poc_user],
            actor=creator,
        )
    return ticket


def _get_creatable_office(creator: User, client_office_id: int) -> ClientOffice:
    """An active Office in the creator's role-specific scope (Client mapping, plus Property for Facility Managers)."""
    office = (
        get_authorized_offices(creator)
        .filter(pk=client_office_id)
        .select_related("property__facility_manager")
        .first()
    )
    if office is None:
        raise ValidationError({"client_office_id": [INVALID_OFFICE_MESSAGE]})
    return office


def _get_issues(issue_ids: list[int]) -> list[Issue]:
    issues = list(Issue.objects.filter(pk__in=issue_ids, is_active=True).select_related("department__poc_user"))
    if len(issues) != len(issue_ids):
        raise ValidationError({"issue_ids": [INVALID_ISSUES_MESSAGE]})
    return issues


def _get_common_department(issues: list[Issue]) -> Department:
    departments = {issue.department_id: issue.department for issue in issues}
    if len(departments) > 1:
        raise ValidationError({"issue_ids": ["Issues cannot belong to multiple departments."]})
    return next(iter(departments.values()))


def _get_affected_floors(office: ClientOffice, submitted_floor_ids: list[int]) -> list[Floor]:
    """Zero mapped Floors: none. One: that Floor automatically. Several: the submitted, required selection."""
    mapped_floors = {floor.id: floor for floor in get_office_floors(office)}
    if not set(submitted_floor_ids) <= set(mapped_floors):
        raise ValidationError({"floor_ids": [INVALID_FLOORS_MESSAGE]})

    if len(mapped_floors) <= 1:
        return list(mapped_floors.values())
    if not submitted_floor_ids:
        raise ValidationError({"floor_ids": ["Select at least one floor."]})
    return [mapped_floors[floor_id] for floor_id in submitted_floor_ids]


# --- Actions on an existing Ticket -------------------------------------------------------------------


def _lock_ticket(actor: User, ticket_id: int) -> Ticket:
    """Lock the Ticket row, then confirm the actor can still see it. Call inside transaction.atomic().

    A separate primary-key query avoids PostgreSQL's FOR UPDATE restrictions on joins
    (readmes/README-authorization.md §5).
    """
    ticket = get_object_or_404(Ticket.objects.select_for_update(), pk=ticket_id)
    if not selectors.get_visible_tickets(actor).filter(pk=ticket.pk).exists():
        raise NotFound()
    return ticket


def _require_current_department_poc(actor: User, ticket: Ticket) -> None:
    if not is_current_department_poc(actor, ticket):
        raise PermissionDenied(NOT_CURRENT_POC_MESSAGE)


@transaction.atomic
def assign_worker(*, ticket_id: int, actor: User, worker_id: int) -> TicketAssignment:
    ticket = _lock_ticket(actor, ticket_id)
    _require_current_department_poc(actor, ticket)
    worker = selectors.get_eligible_workers(ticket).filter(pk=worker_id).first()
    if worker is None:
        raise ValidationError({"worker_id": [INVALID_WORKER_MESSAGE]})
    if not ticket.is_awaiting_worker_assignment or selectors.get_active_assignment(ticket) is not None:
        raise InvalidTicketTransition("Ticket is not awaiting technician assignment.")

    assignment = TicketAssignment.objects.create(ticket=ticket, worker=worker, assigned_by=actor)
    ticket.workflow_stage = WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT
    ticket.save(update_fields=["workflow_stage", "updated_at"])

    activity = record_activity(
        ticket,
        actor,
        ActivityEventType.WORKER_ASSIGNED,
        "assigned technician.",
        metadata={
            "worker_id": worker.id,
            "change": build_change("assignee", "Unassigned", get_name_with_role_label(worker)),
        },
    )
    create_notifications(
        ticket=ticket,
        source_activity=activity,
        event_type=NotificationEventType.WORKER_ASSIGNED,
        recipients=[worker],
        actor=actor,
    )
    return assignment


@transaction.atomic
def change_department(*, ticket_id: int, actor: User, department_id: int, forwarding_note: str) -> Ticket:
    ticket = _lock_ticket(actor, ticket_id)
    _require_current_department_poc(actor, ticket)
    destination = Department.objects.filter(pk=department_id, is_active=True).select_related("poc_user").first()
    if destination is None:
        raise ValidationError({"department_id": [INVALID_DEPARTMENT_MESSAGE]})
    if destination.id == ticket.current_department_id:
        raise ValidationError({"department_id": [SAME_DEPARTMENT_MESSAGE]})
    if not ticket.is_awaiting_worker_assignment:
        raise InvalidTicketTransition("Ticket is not awaiting technician assignment.")

    previous_department = ticket.current_department
    # origin_department is never touched: it records where the Ticket started.
    ticket.current_department = destination
    ticket.save(update_fields=["current_department", "updated_at"])

    activity = record_activity(
        ticket,
        actor,
        ActivityEventType.DEPARTMENT_CHANGED,
        "changed the department.",
        metadata={
            "from_department_id": previous_department.id,
            "to_department_id": destination.id,
            "note": forwarding_note,
            "change": build_change("department", previous_department.name, destination.name),
        },
    )
    create_notifications(
        ticket=ticket,
        source_activity=activity,
        event_type=NotificationEventType.DEPARTMENT_CHANGED,
        recipients=[destination.poc_user],
        actor=actor,
    )
    return ticket


@transaction.atomic
def submit_assessment(*, ticket_id: int, actor: User, outcome: AssessmentOutcome) -> TicketAssessment:
    ticket = _lock_ticket(actor, ticket_id)
    if not is_assigned_worker(actor, selectors.get_active_assignment(ticket)):
        raise PermissionDenied(NOT_ASSIGNED_WORKER_MESSAGE)
    if not ticket.is_awaiting_assessment or TicketAssessment.objects.filter(ticket=ticket).exists():
        raise InvalidTicketTransition("Ticket is not awaiting technician assessment.")

    assessment = TicketAssessment.objects.create(ticket=ticket, submitted_by=actor, outcome=outcome)
    previous_status = ticket.get_status_display()
    ticket.workflow_stage = WorkflowStage.PENDING_DEPARTMENT_POC_REVIEW
    ticket.status = TicketStatus.TECHNICIAN_CLOSED
    ticket.save(update_fields=["workflow_stage", "status", "updated_at"])
    # The Worker's assignment stays active so they remain the displayed assignee during POC review.

    activity = record_activity(
        ticket,
        actor,
        ActivityEventType.ASSESSMENT_SUBMITTED,
        "submitted the assessment.",
        metadata={
            "outcome": outcome,
            "change": build_change("status", previous_status, TicketStatus.TECHNICIAN_CLOSED.label),
        },
    )
    create_notifications(
        ticket=ticket,
        source_activity=activity,
        event_type=NotificationEventType.ASSESSMENT_SUBMITTED,
        recipients=[ticket.current_department.poc_user],
        actor=actor,
    )
    return assessment


@transaction.atomic
def mark_ticket_resolved(*, ticket_id: int, actor: User) -> Ticket:
    ticket = _lock_ticket(actor, ticket_id)
    if not can_mark_resolved(actor, ticket):
        raise PermissionDenied(NOT_ALLOWED_TO_RESOLVE_MESSAGE)
    if ticket.is_closed:
        raise InvalidTicketTransition("Ticket is already closed.")

    previous_status = ticket.get_status_display()
    closed_at = timezone.now()
    ticket.status = TicketStatus.CLOSED
    ticket.closed_by = actor
    ticket.closed_at = closed_at
    # The workflow stage is kept: closing is a separate dimension from where handling stopped.
    ticket.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])

    # The assignment record is kept for history; it just stops being active.
    TicketAssignment.objects.filter(ticket=ticket, ended_at__isnull=True).update(
        ended_at=closed_at, end_reason=AssignmentEndReason.TICKET_CLOSED
    )
    record_activity(
        ticket,
        actor,
        ActivityEventType.TICKET_RESOLVED,
        "marked the ticket as resolved.",
        metadata={"change": build_change("status", previous_status, TicketStatus.CLOSED.label)},
    )
    return ticket


def add_ticket_comment(*, ticket: Ticket, author: User, body: str) -> TicketComment:
    """Any user who can see the Ticket may comment, including after it is closed."""
    return TicketComment.objects.create(ticket=ticket, author=author, body=body)

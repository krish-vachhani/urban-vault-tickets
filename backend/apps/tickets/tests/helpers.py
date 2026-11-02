"""Small builders for ticket test records. Tests never depend on the demo seed command."""

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.organizations.models import Client, ClientOffice, Department, Property
from apps.organizations.tests.helpers import (
    create_client,
    create_department,
    create_office,
    create_property,
    create_user,
    create_worker,
    map_user_to_client,
)
from apps.tickets.models import (
    ActivityEventType,
    AssessmentOutcome,
    AssignmentEndReason,
    Ticket,
    TicketActivity,
    TicketAssessment,
    TicketAssignment,
    TicketStatus,
    WorkflowStage,
)


def create_ticket(**fields) -> Ticket:
    """Create a Ticket, building any related record the caller does not supply."""
    if "client_office" not in fields:
        fields["client_office"] = create_office()
    if "created_by" not in fields:
        fields["created_by"] = create_user(UserRole.CLIENT)
    if "origin_department" not in fields:
        fields["origin_department"] = create_department()
    fields.setdefault("current_department", fields["origin_department"])
    return Ticket.objects.create(**fields)


def create_activity(ticket: Ticket, **fields) -> TicketActivity:
    fields.setdefault("event_type", ActivityEventType.TICKET_CREATED)
    fields.setdefault("description", "created the ticket.")
    return TicketActivity.objects.create(ticket=ticket, **fields)


def create_assignment(ticket: Ticket, worker: User, **fields) -> TicketAssignment:
    fields.setdefault("assigned_by", ticket.current_department.poc_user)
    if "ended_at" in fields:
        # The database requires an assignment to end after it started.
        fields.setdefault("assigned_at", fields["ended_at"] - timedelta(hours=1))
    return TicketAssignment.objects.create(ticket=ticket, worker=worker, **fields)


def create_client_user(client: Client) -> User:
    user = create_user(UserRole.CLIENT)
    map_user_to_client(user, client)
    return user


@dataclass
class TicketScene:
    """One open Ticket with every party that can touch it, all linked consistently.

    The Ticket was created by `client_user` in `office`, which belongs to `client` and
    sits in `property_record` (managed by `facility_manager`). It is routed to `department`.
    """

    client: Client
    client_user: User
    colleague_client_user: User
    facility_manager: User
    property_record: Property
    office: ClientOffice
    department: Department
    poc: User
    worker: User
    ticket: Ticket


def create_scene(**ticket_fields) -> TicketScene:
    facility_manager = create_user(UserRole.FACILITY_MANAGER)
    property_record = create_property(facility_manager)
    client = create_client()
    office = create_office(client, property_record)
    client_user = create_client_user(client)
    department = create_department()
    ticket_fields.setdefault("created_by", client_user)
    ticket = create_ticket(client_office=office, origin_department=department, **ticket_fields)
    return TicketScene(
        client=client,
        client_user=client_user,
        colleague_client_user=create_client_user(client),
        facility_manager=facility_manager,
        property_record=property_record,
        office=office,
        department=department,
        poc=department.poc_user,
        worker=create_worker(department),
        ticket=ticket,
    )


def move_to_assessment_stage(ticket: Ticket, worker: User) -> TicketAssignment:
    """Put the Ticket in the state right after Assign Worker."""
    assignment = create_assignment(ticket, worker)
    ticket.workflow_stage = WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT
    ticket.save()
    return assignment


def move_to_review_stage(ticket: Ticket, worker: User, outcome: str = AssessmentOutcome.FULLY_RESOLVED) -> None:
    """Put the Ticket in the state right after the Worker's assessment (assignment still active)."""
    move_to_assessment_stage(ticket, worker)
    TicketAssessment.objects.create(ticket=ticket, submitted_by=worker, outcome=outcome)
    ticket.workflow_stage = WorkflowStage.PENDING_DEPARTMENT_POC_REVIEW
    ticket.status = TicketStatus.TECHNICIAN_CLOSED
    ticket.save()


def close_ticket(ticket: Ticket, closed_by: User) -> None:
    """Mark the Ticket CLOSED the way the service does, keeping its workflow stage."""
    closed_at = timezone.now()
    ticket.status = TicketStatus.CLOSED
    ticket.closed_by = closed_by
    ticket.closed_at = closed_at
    ticket.save()
    TicketAssignment.objects.filter(ticket=ticket, ended_at__isnull=True).update(
        ended_at=closed_at, end_reason=AssignmentEndReason.TICKET_CLOSED
    )

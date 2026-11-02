"""Demo Tickets covering every workflow state, scenario, and listing behaviour.

Scenarios follow readmes/README-seed-data.md §5. The data is deterministic: the
plan below is a fixed table, and everything else is picked by position (no
randomness). Tickets are written directly, not through the Phase 4 services, so
no NotificationOutbox rows are created for this history.
"""

import itertools
from dataclasses import dataclass
from datetime import datetime, timedelta

from apps.accounts.models import User, UserRole
from apps.organizations.models import ClientOffice, Department, Issue
from apps.organizations.role_labels import get_name_with_role_label
from apps.tickets.demo_seed.reference_data import (
    ABDUL,
    CHAITANYA,
    CHANDAN,
    DHANANJAYA,
    IMRAN,
    KAVYA,
    LAKSHMI,
    MANOJ,
    MEERA,
    NEHA,
    PRAKASH,
    PRIYA,
    RAVI,
    SURESH,
)
from apps.tickets.models import (
    ActivityEventType,
    AssessmentOutcome,
    AssignmentEndReason,
    Ticket,
    TicketActivity,
    TicketAssessment,
    TicketAssignment,
    TicketComment,
    TicketFloor,
    TicketIssue,
    TicketStatus,
    WorkflowStage,
)

ASSIGNMENT = WorkflowStage.PENDING_TECHNICIAN_ASSIGNMENT
ASSESSMENT = WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT
REVIEW = WorkflowStage.PENDING_DEPARTMENT_POC_REVIEW
OPEN = TicketStatus.OPEN
TECHNICIAN_CLOSED = TicketStatus.TECHNICIAN_CLOSED
CLOSED = TicketStatus.CLOSED

# 80 Tickets, 18 hours apart, span about 60 days before the seed date.
HOURS_BETWEEN_TICKETS = 18
HOURS_SINCE_NEWEST_TICKET = 6
# Pause between a Ticket's lifecycle events (shortened for recent Tickets so nothing is in the future).
LIFECYCLE_STEP = timedelta(hours=3)
LIFECYCLE_EVENT_SLOTS = 4  # forward, assign, assess, resolve: the most events one Ticket can have
ROUTING_DELAY = timedelta(seconds=1)

# Lifecycle events after creation, in the order they happen.
FORWARD, ASSIGN, ASSESS, RESOLVE = "forward", "assign", "assess", "resolve"

FORWARDING_NOTE = "This is a network problem, so it belongs with the IT team."


@dataclass(frozen=True)
class PlanRow:
    """`count` Tickets that all end in the same state."""

    count: int
    department: str  # the Department the Issues belong to (the origin Department)
    stage: str
    status: str
    worker_email: str | None = None  # set when a Worker was assigned
    forwarded_to: str | None = None  # set when the Ticket was forwarded to another Department
    creator_email: str | None = None  # set to force a creator; otherwise creators rotate


# The scenario table. Rows with a forced creator guarantee scenarios that must exist:
# Facility Manager-created Tickets resolved at each stage, and a Technical POC's IT Ticket.
TICKET_PLAN = (
    # Technical
    PlanRow(6, "Technical", ASSIGNMENT, OPEN),
    PlanRow(3, "Technical", ASSIGNMENT, OPEN, forwarded_to="IT"),
    PlanRow(2, "Technical", ASSESSMENT, OPEN, worker_email=IMRAN, forwarded_to="IT"),
    PlanRow(9, "Technical", ASSESSMENT, OPEN, worker_email=PRAKASH),
    PlanRow(2, "Technical", ASSESSMENT, OPEN, worker_email=RAVI),
    PlanRow(5, "Technical", REVIEW, TECHNICIAN_CLOSED, worker_email=PRAKASH),
    PlanRow(1, "Technical", REVIEW, TECHNICIAN_CLOSED, worker_email=RAVI),
    PlanRow(3, "Technical", ASSIGNMENT, CLOSED),
    PlanRow(1, "Technical", ASSIGNMENT, CLOSED, creator_email=CHANDAN),
    PlanRow(5, "Technical", ASSESSMENT, CLOSED, worker_email=PRAKASH),
    PlanRow(1, "Technical", ASSESSMENT, CLOSED, worker_email=PRAKASH, creator_email=CHANDAN),
    PlanRow(7, "Technical", REVIEW, CLOSED, worker_email=PRAKASH),
    PlanRow(1, "Technical", REVIEW, CLOSED, worker_email=PRAKASH, creator_email=CHANDAN),
    PlanRow(2, "Technical", REVIEW, CLOSED, worker_email=RAVI),
    # IT
    PlanRow(3, "IT", ASSIGNMENT, OPEN),
    PlanRow(1, "IT", ASSIGNMENT, OPEN, creator_email=DHANANJAYA),
    PlanRow(2, "IT", ASSESSMENT, OPEN, worker_email=IMRAN),
    PlanRow(2, "IT", REVIEW, TECHNICIAN_CLOSED, worker_email=IMRAN),
    PlanRow(1, "IT", ASSIGNMENT, CLOSED),
    PlanRow(1, "IT", ASSESSMENT, CLOSED, worker_email=IMRAN),
    PlanRow(2, "IT", REVIEW, CLOSED, worker_email=IMRAN),
    # Housekeeping
    PlanRow(3, "Housekeeping", ASSIGNMENT, OPEN),
    PlanRow(2, "Housekeeping", ASSESSMENT, OPEN, worker_email=KAVYA),
    PlanRow(1, "Housekeeping", REVIEW, TECHNICIAN_CLOSED, worker_email=KAVYA),
    PlanRow(1, "Housekeeping", ASSIGNMENT, CLOSED),
    PlanRow(1, "Housekeeping", ASSESSMENT, CLOSED, worker_email=KAVYA),
    PlanRow(2, "Housekeeping", REVIEW, CLOSED, worker_email=KAVYA),
    # Electrical
    PlanRow(3, "Electrical", ASSIGNMENT, OPEN),
    PlanRow(2, "Electrical", ASSESSMENT, OPEN, worker_email=MANOJ),
    PlanRow(1, "Electrical", REVIEW, TECHNICIAN_CLOSED, worker_email=MANOJ),
    PlanRow(1, "Electrical", ASSIGNMENT, CLOSED),
    PlanRow(1, "Electrical", ASSESSMENT, CLOSED, worker_email=MANOJ),
    PlanRow(2, "Electrical", REVIEW, CLOSED, worker_email=MANOJ),
)

# (Client Office, creator) pairs that satisfy the creation rules: the creator is mapped to the
# Office's Client, and a Facility Manager manages the Office's Property. Creators rotate through
# this list. Harness is deliberately the most common Client, so its Quick Issues are clear.
CREATION_OPTIONS = (
    ("Harness-1317", CHAITANYA),
    ("Acme-0410", NEHA),
    ("HSR-1317", PRIYA),
    ("Harness-1317", CHANDAN),
    ("Harness-1317", PRIYA),
    ("Acme-2201", NEHA),
    ("HSR-1317", CHAITANYA),
    ("Harness-1317", ABDUL),
    ("Acme-0410", PRIYA),
    ("Harness-1317", CHAITANYA),
    ("HSR-1317", MEERA),
    ("Acme-0410", CHANDAN),
    ("Harness-1317", LAKSHMI),
    ("Acme-2201", SURESH),
    ("Harness-1317", DHANANJAYA),
)

# Issue names for each Department's Tickets, rotating. The four Quick Issues from the wireframe
# (AC not cooling, Internet not working, Pantry not cleaned, Lights flickering) dominate on purpose.
ISSUE_PATTERNS = {
    "Technical": (
        ("AC not cooling",),
        ("AC not cooling",),
        ("Lift not working",),
        ("AC not cooling",),
        ("AC not cooling", "Water leakage"),
        ("AC not cooling",),
        ("AC not cooling",),
        ("AC not cooling",),
        ("AC not cooling",),
        ("AC not cooling",),
        ("AC not cooling",),
        ("AC not cooling",),
    ),
    "IT": (
        ("Internet not working",),
        ("Internet not working", "Wi-Fi slow"),
        ("Printer not working",),
        ("Internet not working",),
        ("Internet not working",),
    ),
    "Housekeeping": (
        ("Pantry not cleaned",),
        ("Pantry not cleaned", "Washroom not cleaned"),
        ("Pantry not cleaned",),
        ("Washroom not cleaned",),
        ("Pantry not cleaned",),
    ),
    "Electrical": (
        ("Lights flickering",),
        ("Lights flickering", "Power outage"),
        ("Lights flickering",),
        ("Power outage",),
        ("Lights flickering",),
    ),
}

DESCRIPTIONS = (
    "Reported during the morning walk-through.",
    "Several people have mentioned this since yesterday.",
    "Needs attention before the next working day.",
    "Please check as soon as possible.",
)
CREATOR_COMMENTS = ("Please treat this as urgent.", "Staff are being affected by this.")
WORKER_COMMENTS = ("Inspected the issue on site.", "Spare part ordered, will update shortly.")
CLOSER_COMMENTS = ("Thanks for the quick resolution.", "Confirmed, the problem is fixed.")


@dataclass(frozen=True)
class TicketSpec:
    """Everything needed to write one Ticket, decided before touching the database."""

    plan: PlanRow
    sequence: int  # 0 is the oldest Ticket
    created_at: datetime
    office_name: str
    creator_email: str
    issue_names: tuple[str, ...]
    assessment_outcome: str | None


def seed_demo_tickets(now: datetime) -> int:
    """Create every demo Ticket and return how many were created."""
    specs = build_ticket_specs(now)
    writer = DemoTicketWriter(now)
    for spec in specs:
        writer.write(spec)
    return len(specs)


def build_ticket_specs(now: datetime) -> list[TicketSpec]:
    plan_rows = _plan_rows_in_chronological_order()
    creation_options = itertools.cycle(CREATION_OPTIONS)
    assessment_outcomes = itertools.cycle(AssessmentOutcome.values)
    issue_positions = {department: 0 for department in ISSUE_PATTERNS}

    specs = []
    for sequence, plan in enumerate(plan_rows):
        if plan.creator_email:
            office_name, creator_email = _first_option_for_creator(plan.creator_email)
        else:
            office_name, creator_email = next(creation_options)

        patterns = ISSUE_PATTERNS[plan.department]
        issue_names = patterns[issue_positions[plan.department] % len(patterns)]
        issue_positions[plan.department] += 1

        hours_old = HOURS_BETWEEN_TICKETS * (len(plan_rows) - 1 - sequence) + HOURS_SINCE_NEWEST_TICKET
        specs.append(
            TicketSpec(
                plan=plan,
                sequence=sequence,
                created_at=now - timedelta(hours=hours_old),
                office_name=office_name,
                creator_email=creator_email,
                issue_names=issue_names,
                assessment_outcome=next(assessment_outcomes) if plan.stage == REVIEW else None,
            )
        )
    return specs


def _plan_rows_in_chronological_order() -> list[PlanRow]:
    """List one entry per Ticket, spreading every row evenly from oldest to newest.

    Without this, all Tickets of one state would be created together and every
    state would sit in one narrow band of dates.
    """
    positioned_rows = []
    for row in TICKET_PLAN:
        for index in range(row.count):
            relative_position = (index + 0.5) / row.count
            positioned_rows.append((relative_position, row))
    positioned_rows.sort(key=lambda positioned_row: positioned_row[0])  # stable: ties keep plan order
    return [row for _, row in positioned_rows]


def _first_option_for_creator(creator_email: str) -> tuple[str, str]:
    return next(option for option in CREATION_OPTIONS if option[1] == creator_email)


class DemoTicketWriter:
    """Writes one demo Ticket and all of its history rows."""

    def __init__(self, now: datetime) -> None:
        self.now = now
        self.users = {user.email: user for user in User.objects.all()}
        self.offices = {office.name: office for office in ClientOffice.objects.select_related("client")}
        self.departments = {
            department.name: department for department in Department.objects.select_related("poc_user")
        }
        self.issues = {issue.name: issue for issue in Issue.objects.all()}

    def write(self, spec: TicketSpec) -> None:
        plan = spec.plan
        creator = self.users[spec.creator_email]
        office = self.offices[spec.office_name]
        origin_department = self.departments[plan.department]
        current_department = self.departments[plan.forwarded_to] if plan.forwarded_to else origin_department
        lifecycle_times = self._lifecycle_times(spec)
        is_closed = plan.status == CLOSED
        closer = self._closer_for(creator, office) if is_closed else None

        ticket = Ticket.objects.create(
            client_office=office,
            created_by=creator,
            origin_department=origin_department,
            current_department=current_department,
            workflow_stage=plan.stage,
            status=plan.status,
            description=self._description_for(spec, creator),
            closed_by=closer,
            closed_at=lifecycle_times.get(RESOLVE),
            created_at=spec.created_at,
        )
        self._attach_issues_and_floors(ticket, spec, office)
        self._record_creation(ticket, creator, origin_department, spec.created_at)

        if plan.forwarded_to:
            self._record_forwarding(ticket, origin_department, current_department, lifecycle_times[FORWARD])
        worker = self.users[plan.worker_email] if plan.worker_email else None
        if worker:
            self._record_assignment(ticket, worker, current_department, lifecycle_times)
        if plan.stage == REVIEW:
            self._record_assessment(ticket, worker, spec.assessment_outcome, lifecycle_times[ASSESS])
        if is_closed:
            self._record_resolution(ticket, closer, lifecycle_times[RESOLVE])

        self._record_comments(ticket, spec, creator, worker, closer, lifecycle_times)

    def _lifecycle_times(self, spec: TicketSpec) -> dict[str, datetime]:
        """Give each lifecycle event this Ticket goes through its own point in time."""
        plan = spec.plan
        events = []
        if plan.forwarded_to:
            events.append(FORWARD)
        if plan.worker_email:
            events.append(ASSIGN)
        if plan.stage == REVIEW:
            events.append(ASSESS)
        if plan.status == CLOSED:
            events.append(RESOLVE)

        step = self._lifecycle_step(spec)
        return {event: spec.created_at + step * (position + 1) for position, event in enumerate(events)}

    def _lifecycle_step(self, spec: TicketSpec) -> timedelta:
        """Pause between lifecycle events, shortened for recent Tickets so nothing lies after the seed time."""
        return min(LIFECYCLE_STEP, (self.now - spec.created_at) / (LIFECYCLE_EVENT_SLOTS + 1))

    def _description_for(self, spec: TicketSpec, creator: User) -> str | None:
        client_may_omit_description = creator.role == UserRole.CLIENT and spec.sequence % 2 == 0
        if client_may_omit_description:
            return None
        return DESCRIPTIONS[spec.sequence % len(DESCRIPTIONS)]

    def _closer_for(self, creator: User, office: ClientOffice) -> User:
        """Clients and Facility Managers resolve their own Tickets; a POC's Ticket is resolved by a Client user."""
        if creator.role != UserRole.DEPARTMENT_POC:
            return creator
        return User.objects.filter(role=UserRole.CLIENT, clients=office.client).order_by("email").first()

    def _attach_issues_and_floors(self, ticket: Ticket, spec: TicketSpec, office: ClientOffice) -> None:
        for issue_name in spec.issue_names:
            TicketIssue.objects.create(ticket=ticket, issue=self.issues[issue_name])

        # No mapped Floors: nothing to attach. One Floor: attached automatically.
        # Several Floors: alternate between "all of them" and "just the first".
        office_floors = list(office.floors.order_by("name"))
        affected_floors = office_floors if spec.sequence % 2 == 0 else office_floors[:1]
        for floor in affected_floors:
            TicketFloor.objects.create(ticket=ticket, floor=floor)

    def _record_creation(self, ticket: Ticket, creator: User, department: Department, created_at: datetime) -> None:
        self._add_activity(ticket, creator, ActivityEventType.TICKET_CREATED, "created the ticket.", created_at)
        self._add_activity(
            ticket,
            None,
            ActivityEventType.TICKET_ROUTED,
            f"Ticket routed to the {department.name} department.",
            created_at + ROUTING_DELAY,
            metadata={"department_id": department.id},
        )

    def _record_forwarding(
        self, ticket: Ticket, from_department: Department, to_department: Department, forwarded_at: datetime
    ) -> None:
        self._add_activity(
            ticket,
            from_department.poc_user,
            ActivityEventType.DEPARTMENT_CHANGED,
            "changed the department.",
            forwarded_at,
            metadata={
                "from_department_id": from_department.id,
                "to_department_id": to_department.id,
                "note": FORWARDING_NOTE,
                "change": _change("department", from_department.name, to_department.name),
            },
        )

    def _record_assignment(
        self, ticket: Ticket, worker: User, department: Department, lifecycle_times: dict[str, datetime]
    ) -> None:
        closed_at = lifecycle_times.get(RESOLVE)
        TicketAssignment.objects.create(
            ticket=ticket,
            worker=worker,
            assigned_by=department.poc_user,
            assigned_at=lifecycle_times[ASSIGN],
            # A resolved Ticket ends its assignment; an assessed-but-open Ticket keeps it active.
            ended_at=closed_at,
            end_reason=AssignmentEndReason.TICKET_CLOSED if closed_at else None,
        )
        self._add_activity(
            ticket,
            department.poc_user,
            ActivityEventType.WORKER_ASSIGNED,
            "assigned technician.",
            lifecycle_times[ASSIGN],
            metadata={
                "worker_id": worker.id,
                "change": _change("assignee", "Unassigned", get_name_with_role_label(worker)),
            },
        )

    def _record_assessment(self, ticket: Ticket, worker: User, outcome: str, submitted_at: datetime) -> None:
        TicketAssessment.objects.create(ticket=ticket, submitted_by=worker, outcome=outcome, submitted_at=submitted_at)
        self._add_activity(
            ticket,
            worker,
            ActivityEventType.ASSESSMENT_SUBMITTED,
            "submitted the assessment.",
            submitted_at,
            metadata={
                "outcome": outcome,
                "change": _change("status", TicketStatus.OPEN.label, TicketStatus.TECHNICIAN_CLOSED.label),
            },
        )

    def _record_resolution(self, ticket: Ticket, closer: User, closed_at: datetime) -> None:
        # A Ticket that reached Pending Department POC Review was Technician Closed before it was resolved.
        was_assessed = ticket.workflow_stage == REVIEW
        previous_status = TicketStatus.TECHNICIAN_CLOSED if was_assessed else TicketStatus.OPEN
        self._add_activity(
            ticket,
            closer,
            ActivityEventType.TICKET_RESOLVED,
            "marked the ticket as resolved.",
            closed_at,
            metadata={"change": _change("status", previous_status.label, TicketStatus.CLOSED.label)},
        )

    def _record_comments(
        self,
        ticket: Ticket,
        spec: TicketSpec,
        creator: User,
        worker: User | None,
        closer: User | None,
        lifecycle_times: dict[str, datetime],
    ) -> None:
        """Add comments from several roles; resolved Tickets also get one after closure.

        Each comment comes half a lifecycle step after the event that prompted it,
        so it sits before the Ticket's next event in the Activity feed.
        """
        half_step = self._lifecycle_step(spec) / 2
        if spec.sequence % 3 == 0:
            comment = CREATOR_COMMENTS[spec.sequence % len(CREATOR_COMMENTS)]
            self._add_comment(ticket, creator, comment, spec.created_at + half_step)
        if worker and spec.sequence % 2 == 0:
            comment = WORKER_COMMENTS[spec.sequence % len(WORKER_COMMENTS)]
            self._add_comment(ticket, worker, comment, lifecycle_times[ASSIGN] + half_step)
        if closer and spec.sequence % 2 == 1:
            comment = CLOSER_COMMENTS[spec.sequence % len(CLOSER_COMMENTS)]
            self._add_comment(ticket, closer, comment, lifecycle_times[RESOLVE] + half_step)

    def _add_activity(
        self,
        ticket: Ticket,
        actor: User | None,
        event_type: str,
        description: str,
        created_at: datetime,
        metadata: dict | None = None,
    ) -> None:
        TicketActivity.objects.create(
            ticket=ticket,
            actor=actor,
            event_type=event_type,
            description=description,
            metadata=metadata or {},
            created_at=created_at,
        )

    def _add_comment(self, ticket: Ticket, author: User, body: str, commented_at: datetime) -> None:
        TicketComment.objects.create(ticket=ticket, author=author, body=body, created_at=commented_at)


def _change(field: str, from_value: str, to_value: str) -> dict[str, str]:
    """Build the display-ready before → after object the History view renders."""
    return {"field": field, "from": from_value, "to": to_value}

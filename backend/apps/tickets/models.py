"""The ticket aggregate: Ticket, its Issues and Floors, assignments, assessment, activity, comments.

Schema reference: readmes/README-database-schema.md §2.11–§2.17.
Lifecycle reference: readmes/README-ticket-lifecycle.md.

Models only declare fields, constraints, and indexes. Every workflow rule that
spans several rows (valid transitions, who may act, same-Department Issues)
lives in the ticket services. Every foreign key uses on_delete=PROTECT so
ticket history can never be deleted by accident.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.accounts.models import UserRole


class WorkflowStage(models.TextChoices):
    PENDING_TECHNICIAN_ASSIGNMENT = "PENDING_TECHNICIAN_ASSIGNMENT", "Pending Technician Assignment"
    PENDING_TECHNICIAN_ASSESSMENT = "PENDING_TECHNICIAN_ASSESSMENT", "Pending Technician Assessment"
    PENDING_DEPARTMENT_POC_REVIEW = "PENDING_DEPARTMENT_POC_REVIEW", "Pending Department POC Review"


class TicketStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    TECHNICIAN_CLOSED = "TECHNICIAN_CLOSED", "Technician Closed"
    CLOSED = "CLOSED", "Closed"


class AssessmentOutcome(models.TextChoices):
    FULLY_RESOLVED = "FULLY_RESOLVED", "Mark Fully Resolved"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED", "Mark Partially Resolved"
    CHANGE_REQUESTED = "CHANGE_REQUESTED", "Suggest Department/Worker Change"


class AssignmentEndReason(models.TextChoices):
    REASSIGNED = "REASSIGNED", "Reassigned to another Worker"
    TICKET_CLOSED = "TICKET_CLOSED", "Ticket was marked resolved"


class ActivityEventType(models.TextChoices):
    TICKET_CREATED = "TICKET_CREATED", "Ticket created"
    TICKET_ROUTED = "TICKET_ROUTED", "Ticket routed"
    WORKER_ASSIGNED = "WORKER_ASSIGNED", "Worker assigned"
    DEPARTMENT_CHANGED = "DEPARTMENT_CHANGED", "Department changed"
    ASSESSMENT_SUBMITTED = "ASSESSMENT_SUBMITTED", "Assessment submitted"
    TICKET_RESOLVED = "TICKET_RESOLVED", "Ticket resolved"


class Ticket(models.Model):
    client_office = models.ForeignKey("organizations.ClientOffice", on_delete=models.PROTECT, related_name="tickets")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_tickets")
    # Never changes after creation: the Department the selected Issues belong to.
    origin_department = models.ForeignKey(
        "organizations.Department", on_delete=models.PROTECT, related_name="origin_tickets"
    )
    # Changes only when the current Department POC forwards the Ticket.
    current_department = models.ForeignKey(
        "organizations.Department", on_delete=models.PROTECT, related_name="current_tickets"
    )
    workflow_stage = models.CharField(
        max_length=40, choices=WorkflowStage.choices, default=WorkflowStage.PENDING_TECHNICIAN_ASSIGNMENT
    )
    status = models.CharField(max_length=20, choices=TicketStatus.choices, default=TicketStatus.OPEN)
    # Optional for Client-created Tickets, required for internally created ones (checked in the creation service).
    description = models.TextField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="closed_tickets"
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    # A default (not auto_now_add) so the demo seed can spread Tickets over time.
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    issues = models.ManyToManyField("organizations.Issue", through="TicketIssue", related_name="tickets")
    floors = models.ManyToManyField("organizations.Floor", through="TicketFloor", related_name="tickets")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        workflow_stage__in=[
                            WorkflowStage.PENDING_TECHNICIAN_ASSIGNMENT,
                            WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT,
                        ],
                        status__in=[TicketStatus.OPEN, TicketStatus.CLOSED],
                    )
                    | Q(
                        workflow_stage=WorkflowStage.PENDING_DEPARTMENT_POC_REVIEW,
                        status__in=[TicketStatus.TECHNICIAN_CLOSED, TicketStatus.CLOSED],
                    )
                ),
                name="ticket_stage_status_is_valid",
            ),
            # CLOSED if and only if both closure fields are set.
            models.CheckConstraint(
                condition=(
                    Q(status=TicketStatus.CLOSED, closed_by__isnull=False, closed_at__isnull=False)
                    | (~Q(status=TicketStatus.CLOSED) & Q(closed_by__isnull=True, closed_at__isnull=True))
                ),
                name="ticket_closure_is_consistent",
            ),
        ]
        indexes = [
            # Department POC listing: current Department, Open/Closed tab, newest or oldest first.
            models.Index(fields=["current_department", "status", "created_at"], name="ticket_dept_status_created"),
            # Client and Facility Manager listing: Office, Open/Closed tab, newest or oldest first.
            models.Index(fields=["client_office", "status", "created_at"], name="ticket_office_status_created"),
        ]

    @property
    def ticket_number(self) -> str:
        return f"TKT-{self.pk}"

    def __str__(self) -> str:
        return self.ticket_number


class TicketIssue(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name="ticket_issues")
    issue = models.ForeignKey("organizations.Issue", on_delete=models.PROTECT, related_name="ticket_issues")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["ticket", "issue"], name="ticketissue_unique_ticket_issue"),
        ]

    def __str__(self) -> str:
        return f"{self.ticket} – {self.issue.name}"


class TicketFloor(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name="ticket_floors")
    floor = models.ForeignKey("organizations.Floor", on_delete=models.PROTECT, related_name="ticket_floors")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["ticket", "floor"], name="ticketfloor_unique_ticket_floor"),
        ]

    def __str__(self) -> str:
        return f"{self.ticket} – {self.floor.name}"


class TicketAssignment(models.Model):
    """One Worker's time on a Ticket. ended_at is null while the assignment is active."""

    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name="assignments")
    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_assignments",
        limit_choices_to={"role": UserRole.WORKER},
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_assignments_made",
        limit_choices_to={"role": UserRole.DEPARTMENT_POC},
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=30, choices=AssignmentEndReason.choices, null=True, blank=True)

    class Meta:
        constraints = [
            # The final database guard behind "at most one active Worker per Ticket".
            models.UniqueConstraint(
                fields=["ticket"],
                condition=Q(ended_at__isnull=True),
                name="ticketassignment_one_active",
            ),
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True) | Q(ended_at__gte=F("assigned_at")),
                name="ticketassignment_end_after_start",
            ),
        ]
        indexes = [
            # Worker visibility: "is this Worker, or was this Worker, assigned to the Ticket?"
            models.Index(fields=["worker", "ticket"], name="ticketassignment_worker_ticket"),
        ]

    def __str__(self) -> str:
        return f"{self.ticket} → {self.worker.name}"


class TicketAssessment(models.Model):
    """The Worker's single assessment of a Ticket. It carries no note; Workers use comments."""

    ticket = models.OneToOneField(Ticket, on_delete=models.PROTECT, related_name="assessment")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="submitted_assessments",
        limit_choices_to={"role": UserRole.WORKER},
    )
    outcome = models.CharField(max_length=30, choices=AssessmentOutcome.choices)
    submitted_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"{self.ticket} – {self.get_outcome_display()}"


class TicketActivity(models.Model):
    """Append-only audit entry. actor is null for system-generated events."""

    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name="activities")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="ticket_activities"
    )
    event_type = models.CharField(max_length=30, choices=ActivityEventType.choices)
    description = models.TextField()
    # Structured details. Events that change the assignee, Department, or status
    # store a display-ready {"field", "from", "to"} object under the "change" key.
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name_plural = "ticket activities"
        indexes = [
            models.Index(fields=["ticket", "created_at"], name="ticketactivity_ticket_created"),
        ]

    def __str__(self) -> str:
        return f"{self.ticket} – {self.event_type}"


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ticket_comments")
    body = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["ticket", "created_at"], name="ticketcomment_ticket_created"),
        ]

    def __str__(self) -> str:
        return f"{self.ticket} – comment by {self.author.name}"

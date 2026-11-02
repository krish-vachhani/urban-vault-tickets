"""Database rules for the ticket schema (readmes/README-database-schema.md §2.11–§2.17, §3, §5)."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import UserRole
from apps.organizations.tests.helpers import (
    create_department,
    create_floor,
    create_issue,
    create_office,
    create_user,
    create_worker,
)
from apps.tickets.models import (
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
from apps.tickets.tests.helpers import create_activity, create_ticket

ASSIGNMENT = WorkflowStage.PENDING_TECHNICIAN_ASSIGNMENT
ASSESSMENT = WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT
REVIEW = WorkflowStage.PENDING_DEPARTMENT_POC_REVIEW


class TicketStageStatusTests(TestCase):
    def closure_fields(self) -> dict:
        return {"closed_by": create_user(UserRole.CLIENT), "closed_at": timezone.now()}

    def test_every_permitted_stage_and_status_combination_is_accepted(self) -> None:
        permitted = [
            (ASSIGNMENT, TicketStatus.OPEN),
            (ASSESSMENT, TicketStatus.OPEN),
            (REVIEW, TicketStatus.TECHNICIAN_CLOSED),
        ]
        for stage, status in permitted:
            with self.subTest(stage=stage, status=status):
                create_ticket(workflow_stage=stage, status=status)

    def test_a_ticket_can_be_closed_at_every_stage(self) -> None:
        for stage in WorkflowStage.values:
            with self.subTest(stage=stage):
                create_ticket(workflow_stage=stage, status=TicketStatus.CLOSED, **self.closure_fields())

    def test_forbidden_stage_and_status_combinations_are_rejected(self) -> None:
        forbidden = [
            (ASSIGNMENT, TicketStatus.TECHNICIAN_CLOSED),
            (ASSESSMENT, TicketStatus.TECHNICIAN_CLOSED),
            (REVIEW, TicketStatus.OPEN),
        ]
        for stage, status in forbidden:
            with self.subTest(stage=stage, status=status):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    create_ticket(workflow_stage=stage, status=status)

    def test_new_ticket_defaults_to_pending_assignment_and_open(self) -> None:
        ticket = create_ticket()

        self.assertEqual(ticket.workflow_stage, ASSIGNMENT)
        self.assertEqual(ticket.status, TicketStatus.OPEN)


class TicketClosureTests(TestCase):
    def test_closed_ticket_must_record_who_closed_it_and_when(self) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_ticket(status=TicketStatus.CLOSED)
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_ticket(status=TicketStatus.CLOSED, closed_at=timezone.now())
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_ticket(status=TicketStatus.CLOSED, closed_by=create_user(UserRole.CLIENT))

    def test_open_ticket_cannot_have_closure_fields(self) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_ticket(closed_by=create_user(UserRole.CLIENT), closed_at=timezone.now())
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_ticket(closed_at=timezone.now())

    def test_fully_closed_ticket_is_accepted(self) -> None:
        ticket = create_ticket(
            status=TicketStatus.CLOSED, closed_by=create_user(UserRole.CLIENT), closed_at=timezone.now()
        )

        self.assertEqual(ticket.status, TicketStatus.CLOSED)


class TicketModelTests(TestCase):
    def test_origin_and_current_department_are_stored_separately(self) -> None:
        origin, destination = create_department(), create_department()
        ticket = create_ticket(origin_department=origin, current_department=destination)
        ticket.refresh_from_db()

        self.assertEqual(ticket.origin_department, origin)
        self.assertEqual(ticket.current_department, destination)

    def test_ticket_number_is_derived_from_the_primary_key(self) -> None:
        ticket = create_ticket()

        self.assertEqual(ticket.ticket_number, f"TKT-{ticket.pk}")

    def test_ticket_with_history_cannot_be_deleted(self) -> None:
        ticket = create_ticket()
        TicketComment.objects.create(ticket=ticket, author=ticket.created_by, body="Please hurry.")

        with self.assertRaises(ProtectedError):
            ticket.delete()

    def test_description_is_optional(self) -> None:
        self.assertIsNone(create_ticket().description)


class TicketRelationTests(TestCase):
    def test_issue_can_be_selected_on_a_ticket_only_once(self) -> None:
        ticket, issue = create_ticket(), create_issue()
        TicketIssue.objects.create(ticket=ticket, issue=issue)

        with self.assertRaises(IntegrityError), transaction.atomic():
            TicketIssue.objects.create(ticket=ticket, issue=issue)

    def test_ticket_can_have_several_issues_and_issues_several_tickets(self) -> None:
        department = create_department()
        first_issue, second_issue = create_issue(department), create_issue(department)
        ticket, other_ticket = create_ticket(origin_department=department), create_ticket(origin_department=department)
        for issue in (first_issue, second_issue):
            TicketIssue.objects.create(ticket=ticket, issue=issue)
        TicketIssue.objects.create(ticket=other_ticket, issue=first_issue)

        self.assertEqual(ticket.issues.count(), 2)
        self.assertEqual(first_issue.tickets.count(), 2)

    def test_floor_can_be_attached_to_a_ticket_only_once(self) -> None:
        office = create_office()
        ticket, floor = create_ticket(client_office=office), create_floor(office.property)
        TicketFloor.objects.create(ticket=ticket, floor=floor)

        with self.assertRaises(IntegrityError), transaction.atomic():
            TicketFloor.objects.create(ticket=ticket, floor=floor)


class TicketAssignmentTests(TestCase):
    def setUp(self) -> None:
        self.department = create_department()
        self.ticket = create_ticket(origin_department=self.department)
        self.worker = create_worker(self.department)
        self.other_worker = create_worker(self.department)

    def assign(self, ticket: Ticket, worker, **fields) -> TicketAssignment:
        return TicketAssignment.objects.create(
            ticket=ticket, worker=worker, assigned_by=self.department.poc_user, **fields
        )

    def test_ticket_cannot_have_two_active_assignments(self) -> None:
        self.assign(self.ticket, self.worker)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.assign(self.ticket, self.other_worker)

    def test_ended_assignment_makes_room_for_a_new_active_one(self) -> None:
        first = self.assign(self.ticket, self.worker)
        first.ended_at = first.assigned_at + timedelta(hours=1)
        first.end_reason = AssignmentEndReason.REASSIGNED
        first.save()

        self.assign(self.ticket, self.other_worker)

        self.assertEqual(self.ticket.assignments.count(), 2)
        self.assertEqual(self.ticket.assignments.filter(ended_at__isnull=True).count(), 1)

    def test_different_tickets_can_each_have_an_active_assignment(self) -> None:
        self.assign(self.ticket, self.worker)
        self.assign(create_ticket(origin_department=self.department), self.worker)

    def test_assignment_cannot_end_before_it_started(self) -> None:
        assigned_at = timezone.now()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.assign(self.ticket, self.worker, assigned_at=assigned_at, ended_at=assigned_at - timedelta(minutes=1))

    def test_assignment_may_end_the_moment_it_started(self) -> None:
        assigned_at = timezone.now()
        self.assign(self.ticket, self.worker, assigned_at=assigned_at, ended_at=assigned_at)

    def test_assignee_must_be_a_worker_and_assigner_a_poc(self) -> None:
        not_a_worker = TicketAssignment(
            ticket=self.ticket, worker=create_user(UserRole.CLIENT), assigned_by=self.department.poc_user
        )
        not_a_poc = TicketAssignment(ticket=self.ticket, worker=self.worker, assigned_by=self.worker)

        with self.assertRaises(ValidationError) as worker_error:
            not_a_worker.full_clean()
        with self.assertRaises(ValidationError) as poc_error:
            not_a_poc.full_clean()
        self.assertIn("worker", worker_error.exception.message_dict)
        self.assertIn("assigned_by", poc_error.exception.message_dict)


class TicketAssessmentTests(TestCase):
    def test_ticket_has_at_most_one_assessment(self) -> None:
        department = create_department()
        ticket, worker = create_ticket(origin_department=department), create_worker(department)
        TicketAssessment.objects.create(ticket=ticket, submitted_by=worker, outcome=AssessmentOutcome.FULLY_RESOLVED)

        with self.assertRaises(IntegrityError), transaction.atomic():
            TicketAssessment.objects.create(
                ticket=ticket, submitted_by=worker, outcome=AssessmentOutcome.CHANGE_REQUESTED
            )


class TicketActivityTests(TestCase):
    def test_metadata_defaults_to_an_empty_object(self) -> None:
        activity = create_activity(create_ticket())
        activity.refresh_from_db()

        self.assertEqual(activity.metadata, {})

    def test_system_events_have_no_actor(self) -> None:
        self.assertIsNone(create_activity(create_ticket(), actor=None).actor)

    def test_metadata_keeps_the_change_object(self) -> None:
        change = {"field": "department", "from": "Technical", "to": "IT"}
        activity = create_activity(create_ticket(), metadata={"change": change})
        activity.refresh_from_db()

        self.assertEqual(activity.metadata["change"], change)


class TicketIndexTests(TestCase):
    def test_listing_and_history_indexes_exist(self) -> None:
        expected_indexes = {
            "tickets_ticket": {"ticket_dept_status_created", "ticket_office_status_created"},
            "tickets_ticketassignment": {"ticketassignment_worker_ticket"},
            "tickets_ticketactivity": {"ticketactivity_ticket_created"},
            "tickets_ticketcomment": {"ticketcomment_ticket_created"},
        }
        with connection.cursor() as cursor:
            for table, index_names in expected_indexes.items():
                with self.subTest(table=table):
                    existing_names = set(connection.introspection.get_constraints(cursor, table))
                    self.assertTrue(index_names <= existing_names)

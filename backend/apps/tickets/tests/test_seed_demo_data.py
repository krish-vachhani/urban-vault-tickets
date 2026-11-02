"""The demo seed command: idempotency, volume targets, scenario coverage, and data integrity.

Targets come from readmes/README-seed-data.md §5–§6.
"""

import os
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Count, Exists, F, OuterRef, Q, QuerySet
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.notifications.models import NotificationOutbox
from apps.organizations.models import ClientOffice, UserClient
from apps.tickets.demo_seed.reference_data import ABDUL, CHAITANYA, CHANDAN, DHANANJAYA, NEHA, PRAKASH
from apps.tickets.models import (
    ActivityEventType,
    AssessmentOutcome,
    Ticket,
    TicketActivity,
    TicketAssignment,
    TicketComment,
    TicketIssue,
    TicketStatus,
    WorkflowStage,
)

DEMO_PASSWORD = "a-local-demo-password"
QUICK_ISSUE_COUNT = 4
WIREFRAME_QUICK_ISSUES = {
    "AC not cooling",
    "Internet not working",
    "Pantry not cleaned",
    "Lights flickering",
}
PRIMARY_ACCOUNTS = [CHAITANYA, CHANDAN, DHANANJAYA, PRAKASH]


def run_seed_command() -> str:
    output = StringIO()
    with mock.patch.dict(os.environ, {"SEED_DEMO_PASSWORD": DEMO_PASSWORD}):
        call_command("seed_demo_data", stdout=output)
    return output.getvalue()


def count_every_project_table() -> dict[str, int]:
    project_labels = ["accounts", "organizations", "tickets", "notifications"]
    return {
        model._meta.label: model.objects.count()
        for label in project_labels
        for model in apps.get_app_config(label).get_models()
    }


def visible_tickets(user: User) -> QuerySet[Ticket]:
    """Tickets the user may see: the role rule OR created by them (readmes/README-authorization.md §1)."""
    if user.role == UserRole.CLIENT:
        role_rule = Exists(UserClient.objects.filter(user=user, client_id=OuterRef("client_office__client_id")))
    elif user.role == UserRole.FACILITY_MANAGER:
        role_rule = Q(client_office__property__facility_manager=user)
    elif user.role == UserRole.DEPARTMENT_POC:
        role_rule = Q(current_department__poc_user=user)
    else:
        role_rule = Exists(TicketAssignment.objects.filter(ticket=OuterRef("pk"), worker=user))
    return Ticket.objects.filter(Q(role_rule) | Q(created_by=user))


# Hashing 14 passwords with the production hasher would make this class slow for no benefit.
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SeedDemoDataTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.first_run_output = run_seed_command()
        cls.table_counts_after_first_run = count_every_project_table()

    def user(self, email: str) -> User:
        return User.objects.get(email=email)

    def test_creates_all_reference_data(self) -> None:
        self.assertEqual(User.objects.count(), 14)
        self.assertEqual(
            {role: User.objects.filter(role=role).count() for role in UserRole.values},
            {UserRole.CLIENT: 3, UserRole.FACILITY_MANAGER: 2, UserRole.DEPARTMENT_POC: 4, UserRole.WORKER: 5},
        )
        counts = self.table_counts_after_first_run
        self.assertEqual(counts["organizations.Client"], 2)
        self.assertEqual(counts["organizations.Property"], 2)
        self.assertEqual(counts["organizations.ClientOffice"], 4)
        self.assertEqual(counts["organizations.Floor"], 7)
        self.assertEqual(counts["organizations.ClientOfficeFloor"], 5)
        self.assertEqual(counts["organizations.Department"], 4)
        self.assertEqual(counts["organizations.DepartmentWorker"], 5)
        self.assertEqual(counts["organizations.Issue"], 10)
        self.assertEqual(counts["tickets.Ticket"], 80)

    def test_demo_accounts_use_the_password_from_the_environment(self) -> None:
        for user in User.objects.all():
            with self.subTest(email=user.email):
                self.assertTrue(user.check_password(DEMO_PASSWORD))

    def test_running_again_creates_no_duplicates(self) -> None:
        second_run_output = run_seed_command()

        self.assertEqual(count_every_project_table(), self.table_counts_after_first_run)
        self.assertIn("Tickets already exist", second_run_output)

    def test_command_refuses_to_run_without_a_demo_password(self) -> None:
        with mock.patch.dict(os.environ, {"SEED_DEMO_PASSWORD": ""}):
            with self.assertRaises(CommandError):
                call_command("seed_demo_data", stdout=StringIO())

    def test_seeding_writes_no_notification_outbox_rows(self) -> None:
        self.assertEqual(NotificationOutbox.objects.count(), 0)

    def test_primary_accounts_have_at_least_twelve_tickets_in_each_tab(self) -> None:
        """Twelve is more than one page of ten, so every primary account sees at least two pages per tab."""
        for email in PRIMARY_ACCOUNTS:
            tickets = visible_tickets(self.user(email))
            with self.subTest(email=email):
                self.assertGreaterEqual(tickets.exclude(status=TicketStatus.CLOSED).count(), 12)
                self.assertGreaterEqual(tickets.filter(status=TicketStatus.CLOSED).count(), 12)

    def test_neha_cannot_see_any_harness_ticket(self) -> None:
        neha_tickets = visible_tickets(self.user(NEHA))

        self.assertGreater(neha_tickets.count(), 0)
        self.assertFalse(neha_tickets.filter(client_office__client__name="Harness").exists())

    def test_chandan_can_create_only_in_harness_1317_for_harness(self) -> None:
        offices = ClientOffice.objects.filter(client__name="Harness", property__facility_manager__email=CHANDAN)

        self.assertEqual(list(offices.values_list("name", flat=True)), ["Harness-1317"])

    def test_harness_quick_issues_are_the_four_wireframe_issues(self) -> None:
        issue_counts = list(
            TicketIssue.objects.filter(ticket__client_office__client__name="Harness")
            .values("issue__name")
            .annotate(uses=Count("id"))
            .order_by("-uses")
        )

        top_four = {entry["issue__name"] for entry in issue_counts[:QUICK_ISSUE_COUNT]}
        self.assertEqual(top_four, WIREFRAME_QUICK_ISSUES)
        # Strictly more frequent than the fifth issue, so the recency tie-breaker never decides.
        self.assertGreater(issue_counts[QUICK_ISSUE_COUNT - 1]["uses"], issue_counts[QUICK_ISSUE_COUNT]["uses"])

    def test_tickets_cover_every_workflow_state(self) -> None:
        states = set(Ticket.objects.values_list("workflow_stage", "status"))

        self.assertEqual(
            states,
            {
                (WorkflowStage.PENDING_TECHNICIAN_ASSIGNMENT, TicketStatus.OPEN),
                (WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT, TicketStatus.OPEN),
                (WorkflowStage.PENDING_DEPARTMENT_POC_REVIEW, TicketStatus.TECHNICIAN_CLOSED),
                (WorkflowStage.PENDING_TECHNICIAN_ASSIGNMENT, TicketStatus.CLOSED),
                (WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT, TicketStatus.CLOSED),
                (WorkflowStage.PENDING_DEPARTMENT_POC_REVIEW, TicketStatus.CLOSED),
            },
        )

    def test_all_three_assessment_outcomes_are_waiting_for_review(self) -> None:
        outcomes = Ticket.objects.filter(status=TicketStatus.TECHNICIAN_CLOSED).values_list(
            "assessment__outcome", flat=True
        )

        self.assertEqual(set(outcomes), set(AssessmentOutcome.values))

    def test_closed_tickets_at_each_stage_include_client_and_facility_manager_resolutions(self) -> None:
        for stage in WorkflowStage.values:
            closer_roles = set(
                Ticket.objects.filter(status=TicketStatus.CLOSED, workflow_stage=stage).values_list(
                    "closed_by__role", flat=True
                )
            )
            with self.subTest(stage=stage):
                self.assertLessEqual({UserRole.CLIENT, UserRole.FACILITY_MANAGER}, closer_roles)

    def test_forwarded_tickets_keep_their_origin_department_and_record_the_note(self) -> None:
        forwarded = Ticket.objects.exclude(origin_department=F("current_department"))

        self.assertGreater(forwarded.count(), 0)
        for ticket in forwarded:
            activity = ticket.activities.get(event_type=ActivityEventType.DEPARTMENT_CHANGED)
            with self.subTest(ticket=ticket.ticket_number):
                self.assertEqual(ticket.origin_department.name, "Technical")
                self.assertEqual(ticket.current_department.name, "IT")
                self.assertTrue(activity.metadata["note"])
                self.assertEqual(activity.metadata["change"], {"field": "department", "from": "Technical", "to": "IT"})

    def test_prakash_keeps_visibility_of_closed_tickets_he_was_assigned(self) -> None:
        historical = TicketAssignment.objects.filter(
            worker__email=PRAKASH, ended_at__isnull=False, ticket__status=TicketStatus.CLOSED
        )

        self.assertGreater(historical.count(), 0)
        prakash_closed_tickets = visible_tickets(self.user(PRAKASH)).filter(status=TicketStatus.CLOSED)
        self.assertEqual(prakash_closed_tickets.count(), historical.count())

    def test_technical_poc_created_tickets_that_route_to_it(self) -> None:
        tickets = Ticket.objects.filter(created_by__email=DHANANJAYA, origin_department__name="IT")

        self.assertGreater(tickets.count(), 0)
        for ticket in tickets:
            with self.subTest(ticket=ticket.ticket_number):
                self.assertEqual(ticket.current_department.poc_user.email, ABDUL)
                self.assertIn(ticket, visible_tickets(self.user(DHANANJAYA)))

    def test_some_tickets_have_two_issues_from_one_department(self) -> None:
        two_issue_tickets = Ticket.objects.annotate(issue_count=Count("issues")).filter(issue_count=2)

        self.assertGreater(two_issue_tickets.count(), 0)

    def test_comments_come_from_several_roles_and_include_some_after_closure(self) -> None:
        comment_roles = set(TicketComment.objects.values_list("author__role", flat=True))
        comments_after_closure = TicketComment.objects.filter(
            ticket__closed_at__isnull=False, created_at__gt=F("ticket__closed_at")
        )

        self.assertLessEqual({UserRole.CLIENT, UserRole.WORKER}, comment_roles)
        self.assertGreater(comments_after_closure.count(), 0)

    def test_only_the_resolver_comments_after_a_ticket_was_closed(self) -> None:
        for ticket in Ticket.objects.filter(status=TicketStatus.CLOSED):
            late_comment_authors = set(
                ticket.comments.filter(created_at__gt=ticket.closed_at).values_list("author_id", flat=True)
            )
            with self.subTest(ticket=ticket.ticket_number):
                self.assertLessEqual(late_comment_authors, {ticket.closed_by_id})

    def test_worker_comments_come_before_the_assessment_and_the_resolution(self) -> None:
        worker_comments = TicketComment.objects.filter(author__role=UserRole.WORKER).select_related("ticket")

        self.assertGreater(worker_comments.count(), 0)
        for comment in worker_comments:
            ticket = comment.ticket
            later_events = [ticket.closed_at] if ticket.closed_at else []
            if hasattr(ticket, "assessment"):
                later_events.append(ticket.assessment.submitted_at)
            with self.subTest(ticket=ticket.ticket_number):
                self.assertTrue(all(comment.created_at < event_time for event_time in later_events))

    def test_every_listing_filter_and_issue_search_narrows_some_primary_accounts_tickets(self) -> None:
        """Seed README §6: for each filter, a primary account needs two or more values to choose between."""
        filter_fields = {
            "Client": "client_office__client",
            "Current Department": "current_department",
            "Facility Manager": "client_office__property__facility_manager",
            "Workflow stage": "workflow_stage",
        }
        for filter_name, field in filter_fields.items():
            distinct_value_counts = [
                visible_tickets(self.user(email)).values(field).distinct().count() for email in PRIMARY_ACCOUNTS
            ]
            with self.subTest(filter=filter_name):
                self.assertGreaterEqual(max(distinct_value_counts), 2)

        chandan_tickets = visible_tickets(self.user(CHANDAN))
        searched_tickets = chandan_tickets.filter(issues__name__icontains="Internet")
        self.assertGreater(searched_tickets.count(), 0)
        self.assertLess(searched_tickets.count(), chandan_tickets.count())

    def test_tickets_are_spread_over_about_sixty_days(self) -> None:
        now = timezone.now()
        ages = [now - created_at for created_at in Ticket.objects.values_list("created_at", flat=True)]

        self.assertGreater(max(ages), timedelta(days=55))
        self.assertLess(max(ages), timedelta(days=61))
        self.assertLess(min(ages), timedelta(days=1))

    def test_a_created_assigned_and_assessed_ticket_has_four_activity_entries(self) -> None:
        ticket = Ticket.objects.annotate(activity_count=Count("activities")).filter(
            status=TicketStatus.TECHNICIAN_CLOSED, origin_department=F("current_department")
        )

        self.assertGreater(ticket.count(), 0)
        self.assertEqual(set(ticket.values_list("activity_count", flat=True)), {4})

    def test_initial_routing_history_names_the_original_department_poc(self) -> None:
        routed_events = TicketActivity.objects.filter(event_type=ActivityEventType.TICKET_ROUTED).select_related(
            "ticket__origin_department__poc_user"
        )
        self.assertEqual(routed_events.count(), Ticket.objects.count())
        for event in routed_events:
            department = event.ticket.origin_department
            with self.subTest(ticket=event.ticket_id):
                self.assertEqual(event.metadata["department_id"], department.id)
                self.assertEqual(event.metadata["change"], {
                    "field": "assignee", "from": "Unassigned",
                    "to": f"{department.poc_user.name} ({department.name} Manager)",
                })


class SeededTicketIntegrityTests(TestCase):
    """The cross-table rules the database cannot enforce must still hold for every seeded Ticket."""

    @classmethod
    def setUpTestData(cls) -> None:
        with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
            run_seed_command()
        cls.seed_finished_at = timezone.now()

    def test_every_ticket_follows_the_creation_rules(self) -> None:
        for ticket in Ticket.objects.select_related("client_office__client", "client_office__property", "created_by"):
            client = ticket.client_office.client
            creator = ticket.created_by
            with self.subTest(ticket=ticket.ticket_number):
                self.assertTrue(UserClient.objects.filter(user=creator, client=client).exists())
                if creator.role == UserRole.FACILITY_MANAGER:
                    self.assertEqual(ticket.client_office.property.facility_manager, creator)
                if creator.role != UserRole.CLIENT:
                    self.assertTrue(ticket.description)

    def test_every_ticket_has_issues_from_its_origin_department_and_floors_from_its_office(self) -> None:
        for ticket in Ticket.objects.all():
            issue_department_ids = set(ticket.issues.values_list("department_id", flat=True))
            office_floor_ids = set(ticket.client_office.floors.values_list("id", flat=True))
            ticket_floor_ids = set(ticket.floors.values_list("id", flat=True))
            with self.subTest(ticket=ticket.ticket_number):
                self.assertEqual(issue_department_ids, {ticket.origin_department_id})
                self.assertTrue(ticket_floor_ids <= office_floor_ids)
                self.assertEqual(bool(ticket_floor_ids), bool(office_floor_ids))

    def test_every_assignment_is_consistent_with_its_ticket(self) -> None:
        for ticket in Ticket.objects.prefetch_related("assignments"):
            assignments = list(ticket.assignments.all())
            active_assignments = [assignment for assignment in assignments if assignment.ended_at is None]
            with self.subTest(ticket=ticket.ticket_number):
                for assignment in assignments:
                    department_workers = ticket.current_department.worker_memberships
                    self.assertTrue(department_workers.filter(worker=assignment.worker).exists())
                    self.assertEqual(assignment.assigned_by, ticket.current_department.poc_user)
                if ticket.status == TicketStatus.CLOSED:
                    self.assertEqual(active_assignments, [])
                    self.assertTrue(all(a.end_reason for a in assignments))
                else:
                    self.assertEqual(len(active_assignments), len(assignments))

    def test_assignment_and_assessment_match_the_workflow_stage(self) -> None:
        for ticket in Ticket.objects.all():
            has_assignment = ticket.assignments.exists()
            has_assessment = hasattr(ticket, "assessment")
            with self.subTest(ticket=ticket.ticket_number):
                if ticket.workflow_stage == WorkflowStage.PENDING_TECHNICIAN_ASSIGNMENT:
                    self.assertFalse(has_assignment or has_assessment)
                elif ticket.workflow_stage == WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT:
                    self.assertTrue(has_assignment)
                    self.assertFalse(has_assessment)
                else:
                    self.assertTrue(has_assignment and has_assessment)
                    self.assertEqual(ticket.assessment.submitted_by, ticket.assignments.get().worker)

    def test_closed_tickets_were_resolved_by_a_mapped_client_user_or_their_creator(self) -> None:
        for ticket in Ticket.objects.filter(status=TicketStatus.CLOSED).select_related("closed_by", "client_office"):
            is_mapped_client_user = (
                ticket.closed_by.role == UserRole.CLIENT
                and UserClient.objects.filter(user=ticket.closed_by, client_id=ticket.client_office.client_id).exists()
            )
            with self.subTest(ticket=ticket.ticket_number):
                self.assertTrue(is_mapped_client_user or ticket.closed_by_id == ticket.created_by_id)
                self.assertTrue(ticket.activities.filter(event_type=ActivityEventType.TICKET_RESOLVED).exists())

    def test_no_history_row_lies_in_the_future_or_before_its_ticket(self) -> None:
        for ticket in Ticket.objects.all():
            timestamps = [activity.created_at for activity in ticket.activities.all()]
            timestamps += [comment.created_at for comment in ticket.comments.all()]
            with self.subTest(ticket=ticket.ticket_number):
                self.assertGreaterEqual(min(timestamps), ticket.created_at)
                self.assertLessEqual(max(timestamps), self.seed_finished_at)

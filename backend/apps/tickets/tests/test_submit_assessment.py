from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.notifications.models import NotificationEventType, NotificationOutbox
from apps.organizations.tests.helpers import create_department, create_worker
from apps.tickets import services
from apps.tickets.models import (
    ActivityEventType,
    AssessmentOutcome,
    TicketActivity,
    TicketAssessment,
    TicketAssignment,
    TicketStatus,
    WorkflowStage,
)
from apps.tickets.tests.helpers import (
    close_ticket,
    create_assignment,
    create_scene,
    move_to_assessment_stage,
    move_to_review_stage,
)


def assessment_url(ticket_id) -> str:
    return f"/api/v1/tickets/{ticket_id}/submit-assessment/"


class SubmitAssessmentTests(APITestCase):
    def setUp(self) -> None:
        self.scene = create_scene()
        self.ticket = self.scene.ticket
        move_to_assessment_stage(self.ticket, self.scene.worker)

    def submit(self, user, outcome=AssessmentOutcome.FULLY_RESOLVED, ticket_id=None):
        self.client.force_authenticate(user)
        return self.client.post(assessment_url(ticket_id or self.ticket.id), {"outcome": outcome}, format="json")

    def assert_no_assessment(self) -> None:
        self.ticket.refresh_from_db()
        self.assertFalse(TicketAssessment.objects.exists())
        self.assertEqual(self.ticket.workflow_stage, WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT)
        self.assertEqual(self.ticket.status, TicketStatus.OPEN)
        self.assertFalse(TicketActivity.objects.exists())
        self.assertFalse(NotificationOutbox.objects.exists())

    def test_every_outcome_moves_the_ticket_to_poc_review_as_technician_closed(self) -> None:
        for outcome in AssessmentOutcome.values:
            with self.subTest(outcome=outcome):
                scene = create_scene()
                move_to_assessment_stage(scene.ticket, scene.worker)

                response = self.submit(scene.worker, outcome, ticket_id=scene.ticket.id)

                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertEqual(
                    response.json(),
                    {
                        "ticket_id": scene.ticket.id,
                        "outcome": outcome,
                        "workflow_stage": "PENDING_DEPARTMENT_POC_REVIEW",
                        "status": "TECHNICIAN_CLOSED",
                    },
                )
                scene.ticket.refresh_from_db()
                self.assertEqual(scene.ticket.workflow_stage, WorkflowStage.PENDING_DEPARTMENT_POC_REVIEW)
                self.assertEqual(scene.ticket.status, TicketStatus.TECHNICIAN_CLOSED)
                assessment = TicketAssessment.objects.get(ticket=scene.ticket)
                self.assertEqual((assessment.outcome, assessment.submitted_by), (outcome, scene.worker))

    def test_assignment_stays_active_and_the_ticket_stays_in_the_open_tab(self) -> None:
        self.submit(self.scene.worker)

        self.assertTrue(TicketAssignment.objects.get(ticket=self.ticket).ended_at is None)
        self.client.force_authenticate(self.scene.client_user)
        listed = self.client.get("/api/v1/tickets/", {"tab": "open"}).json()["results"]
        self.assertEqual([item["id"] for item in listed], [self.ticket.id])
        self.assertEqual(listed[0]["current_assignees"][-1]["id"], self.scene.worker.id)

    def test_one_activity_records_the_outcome_and_the_status_change_and_the_poc_is_notified(self) -> None:
        self.submit(self.scene.worker, AssessmentOutcome.PARTIALLY_RESOLVED)

        activity = TicketActivity.objects.get()
        self.assertEqual(activity.event_type, ActivityEventType.ASSESSMENT_SUBMITTED)
        self.assertEqual(activity.actor, self.scene.worker)
        self.assertEqual(
            activity.metadata,
            {
                "outcome": "PARTIALLY_RESOLVED",
                "change": {"field": "status", "from": "Open", "to": "Technician Closed"},
            },
        )
        notification = NotificationOutbox.objects.get()
        self.assertEqual(notification.recipient, self.scene.poc)
        self.assertEqual(notification.source_activity, activity)
        self.assertEqual(notification.event_type, NotificationEventType.ASSESSMENT_SUBMITTED)

    def test_unknown_or_missing_outcome_is_a_validation_error(self) -> None:
        self.client.force_authenticate(self.scene.worker)

        for payload in ({}, {"outcome": "DONE"}, {"outcome": ""}):
            with self.subTest(payload=payload):
                response = self.client.post(assessment_url(self.ticket.id), payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("outcome", response.json()["error"]["details"])
        self.assert_no_assessment()

    def test_submitting_a_second_time_is_a_409_and_creates_no_second_assessment(self) -> None:
        self.submit(self.scene.worker, AssessmentOutcome.FULLY_RESOLVED)

        response = self.submit(self.scene.worker, AssessmentOutcome.CHANGE_REQUESTED)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["error"]["code"], "INVALID_TICKET_TRANSITION")
        self.assertEqual(TicketAssessment.objects.get().outcome, AssessmentOutcome.FULLY_RESOLVED)
        self.assertEqual(TicketActivity.objects.count(), 1)

    def test_visible_users_who_are_not_the_assigned_worker_get_403(self) -> None:
        other_worker = create_worker(self.scene.department)
        create_assignment(
            self.ticket, other_worker, ended_at=timezone.now(), end_reason="REASSIGNED", assigned_at=self.ticket.created_at
        )
        for user in (self.scene.poc, self.scene.client_user, self.scene.facility_manager, other_worker):
            with self.subTest(role=user.role, user=user.id):
                response = self.submit(user)

                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(response.json()["error"]["code"], "PERMISSION_DENIED")
        self.assert_no_assessment()

    def test_a_historical_worker_can_view_the_ticket_but_not_submit(self) -> None:
        historical_worker = self.scene.worker
        TicketAssignment.objects.update(ended_at=timezone.now(), end_reason="REASSIGNED")
        replacement = create_worker(self.scene.department)
        create_assignment(self.ticket, replacement)

        self.client.force_authenticate(historical_worker)
        self.assertEqual(self.client.get(f"/api/v1/tickets/{self.ticket.id}/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.submit(historical_worker).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.submit(replacement).status_code, status.HTTP_201_CREATED)

    def test_worker_without_access_to_the_ticket_gets_404(self) -> None:
        unassigned_worker = create_worker(self.scene.department)

        response = self.submit(unassigned_worker)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), self.submit(unassigned_worker, ticket_id=999999).json())
        self.assert_no_assessment()

    def test_permission_is_checked_before_the_body(self) -> None:
        self.client.force_authenticate(self.scene.poc)

        response = self.client.post(assessment_url(self.ticket.id), {"outcome": "nonsense"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ticket_that_is_not_at_the_assessment_stage_is_a_409(self) -> None:
        scene = create_scene()
        move_to_review_stage(scene.ticket, scene.worker)

        response = self.submit(scene.worker, ticket_id=scene.ticket.id)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_a_closed_ticket_cannot_be_assessed(self) -> None:
        close_ticket(self.ticket, self.scene.client_user)

        # Closing ended the assignment, so the Worker is only a historical one now.
        self.assertEqual(self.submit(self.scene.worker).status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(TicketAssessment.objects.exists())

    def test_failure_after_the_assessment_is_written_rolls_everything_back(self) -> None:
        with patch.object(services, "create_notifications", side_effect=RuntimeError("outbox unavailable")):
            with self.assertRaises(RuntimeError):
                services.submit_assessment(
                    ticket_id=self.ticket.id, actor=self.scene.worker, outcome=AssessmentOutcome.FULLY_RESOLVED
                )

        self.assert_no_assessment()


class OtherDepartmentIsolationTest(APITestCase):
    def test_a_worker_of_another_department_cannot_reach_the_ticket(self) -> None:
        scene = create_scene()
        move_to_assessment_stage(scene.ticket, scene.worker)
        foreign_worker = create_worker(create_department())

        self.client.force_authenticate(foreign_worker)
        response = self.client.post(assessment_url(scene.ticket.id), {"outcome": "FULLY_RESOLVED"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

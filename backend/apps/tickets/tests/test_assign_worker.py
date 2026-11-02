from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.notifications.models import NotificationEventType, NotificationOutbox
from apps.organizations.tests.helpers import create_department, create_worker
from apps.tickets import services
from apps.tickets.models import ActivityEventType, TicketActivity, TicketAssignment, WorkflowStage
from apps.tickets.tests.helpers import close_ticket, create_scene, move_to_assessment_stage


def assign_url(ticket_id) -> str:
    return f"/api/v1/tickets/{ticket_id}/assign-worker/"


class AssignWorkerTests(APITestCase):
    def setUp(self) -> None:
        self.scene = create_scene()
        self.ticket = self.scene.ticket

    def assign(self, user, worker_id, ticket_id=None):
        self.client.force_authenticate(user)
        return self.client.post(assign_url(ticket_id or self.ticket.id), {"worker_id": worker_id}, format="json")

    def assert_unchanged(self) -> None:
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.workflow_stage, WorkflowStage.PENDING_TECHNICIAN_ASSIGNMENT)
        self.assertFalse(TicketAssignment.objects.exists())
        self.assertFalse(TicketActivity.objects.exists())
        self.assertFalse(NotificationOutbox.objects.exists())

    def test_current_poc_assigns_a_worker_of_the_department(self) -> None:
        response = self.assign(self.scene.poc, self.scene.worker.id)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.json(),
            {
                "message": "Worker assigned successfully.",
                "ticket_id": self.ticket.id,
                "workflow_stage": "PENDING_TECHNICIAN_ASSESSMENT",
                "worker": {
                    "id": self.scene.worker.id,
                    "name": self.scene.worker.name,
                    "role": "WORKER",
                    "role_label": "Technician",
                },
            },
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.workflow_stage, WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT)
        self.assertEqual(self.ticket.status, "OPEN")
        assignment = TicketAssignment.objects.get()
        self.assertEqual((assignment.worker, assignment.assigned_by), (self.scene.worker, self.scene.poc))
        self.assertIsNone(assignment.ended_at)

    def test_assignment_records_activity_and_notifies_only_the_worker(self) -> None:
        self.assign(self.scene.poc, self.scene.worker.id)

        activity = TicketActivity.objects.get()
        self.assertEqual(activity.event_type, ActivityEventType.WORKER_ASSIGNED)
        self.assertEqual(activity.actor, self.scene.poc)
        self.assertEqual(
            activity.metadata,
            {
                "worker_id": self.scene.worker.id,
                "change": {
                    "field": "assignee",
                    "from": "Unassigned",
                    "to": f"{self.scene.worker.name} (Technician)",
                },
            },
        )
        notification = NotificationOutbox.objects.get()
        self.assertEqual(notification.recipient, self.scene.worker)
        self.assertEqual(notification.source_activity, activity)
        self.assertEqual(notification.event_type, NotificationEventType.WORKER_ASSIGNED)

    def test_the_assigned_worker_can_now_see_the_ticket(self) -> None:
        self.assign(self.scene.poc, self.scene.worker.id)

        self.client.force_authenticate(self.scene.worker)
        self.assertEqual(self.client.get(f"/api/v1/tickets/{self.ticket.id}/").status_code, status.HTTP_200_OK)

    def test_user_outside_the_visibility_scope_gets_404(self) -> None:
        outsider_poc = create_department().poc_user

        response = self.assign(outsider_poc, self.scene.worker.id)
        unknown = self.assign(outsider_poc, self.scene.worker.id, ticket_id=999999)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), unknown.json())
        self.assert_unchanged()

    def test_visible_users_who_are_not_the_current_poc_get_403(self) -> None:
        for user in (self.scene.client_user, self.scene.facility_manager):
            with self.subTest(role=user.role):
                response = self.assign(user, self.scene.worker.id)

                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(response.json()["error"]["code"], "PERMISSION_DENIED")
        self.assert_unchanged()

    def test_poc_of_another_department_who_created_the_ticket_gets_403(self) -> None:
        other_poc = create_department().poc_user
        self.ticket.created_by = other_poc
        self.ticket.save()

        self.assertEqual(self.assign(other_poc, self.scene.worker.id).status_code, status.HTTP_403_FORBIDDEN)
        self.assert_unchanged()

    def test_permission_is_checked_before_the_body(self) -> None:
        self.client.force_authenticate(self.scene.client_user)

        response = self.client.post(assign_url(self.ticket.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_worker_must_exist_be_active_and_belong_to_the_current_department(self) -> None:
        inactive_worker = create_worker(self.scene.department)
        inactive_worker.is_active = False
        inactive_worker.save()
        cases = {
            "another department": create_worker(create_department()).id,
            "inactive": inactive_worker.id,
            "unknown": 999999,
            "a poc": self.scene.poc.id,
        }

        for name, worker_id in cases.items():
            with self.subTest(case=name):
                response = self.assign(self.scene.poc, worker_id)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("worker_id", response.json()["error"]["details"])
        self.assert_unchanged()

    def test_missing_or_malformed_worker_id_is_a_validation_error(self) -> None:
        self.client.force_authenticate(self.scene.poc)

        for payload in ({}, {"worker_id": "abc"}, {"worker_id": None}):
            with self.subTest(payload=payload):
                response = self.client.post(assign_url(self.ticket.id), payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assigning_twice_is_a_409_and_keeps_a_single_active_assignment(self) -> None:
        self.assign(self.scene.poc, self.scene.worker.id)
        second_worker = create_worker(self.scene.department)

        response = self.assign(self.scene.poc, second_worker.id)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["error"]["code"], "INVALID_TICKET_TRANSITION")
        self.assertEqual(TicketAssignment.objects.filter(ended_at__isnull=True).count(), 1)
        self.assertEqual(TicketActivity.objects.count(), 1)

    def test_closed_ticket_cannot_be_assigned(self) -> None:
        close_ticket(self.ticket, self.scene.client_user)

        response = self.assign(self.scene.poc, self.scene.worker.id)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assert_no_assignment()

    def test_ticket_past_the_assignment_stage_cannot_be_assigned_again(self) -> None:
        move_to_assessment_stage(self.ticket, self.scene.worker)
        TicketAssignment.objects.update(ended_at=self.ticket.created_at, assigned_at=self.ticket.created_at)

        response = self.assign(self.scene.poc, create_worker(self.scene.department).id)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def assert_no_assignment(self) -> None:
        self.assertFalse(TicketAssignment.objects.exists())

    def test_failure_after_the_assignment_is_written_rolls_everything_back(self) -> None:
        with patch.object(services, "create_notifications", side_effect=RuntimeError("outbox unavailable")):
            with self.assertRaises(RuntimeError):
                services.assign_worker(ticket_id=self.ticket.id, actor=self.scene.poc, worker_id=self.scene.worker.id)

        self.assert_unchanged()

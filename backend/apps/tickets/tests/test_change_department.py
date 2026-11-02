from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.notifications.models import NotificationEventType, NotificationOutbox
from apps.organizations.tests.helpers import create_department
from apps.tickets import services
from apps.tickets.models import ActivityEventType, TicketActivity, WorkflowStage
from apps.tickets.tests.helpers import close_ticket, create_scene, move_to_assessment_stage

NOTE = "This looks like an IT infrastructure problem."


def change_url(ticket_id) -> str:
    return f"/api/v1/tickets/{ticket_id}/change-department/"


class ChangeDepartmentTests(APITestCase):
    def setUp(self) -> None:
        self.scene = create_scene()
        self.ticket = self.scene.ticket
        self.destination = create_department()

    def change(self, user, department_id=None, note=NOTE, ticket_id=None):
        self.client.force_authenticate(user)
        payload = {"department_id": department_id or self.destination.id, "forwarding_note": note}
        return self.client.post(change_url(ticket_id or self.ticket.id), payload, format="json")

    def assert_unchanged(self) -> None:
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.current_department, self.scene.department)
        self.assertFalse(TicketActivity.objects.exists())
        self.assertFalse(NotificationOutbox.objects.exists())

    def test_current_poc_forwards_the_ticket(self) -> None:
        response = self.change(self.scene.poc)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "ticket_id": self.ticket.id,
                "current_department": {"id": self.destination.id, "name": self.destination.name},
                "workflow_stage": "PENDING_TECHNICIAN_ASSIGNMENT",
                "status": "OPEN",
            },
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.current_department, self.destination)
        self.assertEqual(self.ticket.origin_department, self.scene.department, "origin is never rewritten")
        self.assertEqual(self.ticket.workflow_stage, WorkflowStage.PENDING_TECHNICIAN_ASSIGNMENT)
        self.assertEqual(self.ticket.status, "OPEN")

    def test_forwarding_records_the_note_and_notifies_the_destination_poc(self) -> None:
        self.change(self.scene.poc)

        activity = TicketActivity.objects.get()
        self.assertEqual(activity.event_type, ActivityEventType.DEPARTMENT_CHANGED)
        self.assertEqual(activity.actor, self.scene.poc)
        self.assertEqual(
            activity.metadata,
            {
                "from_department_id": self.scene.department.id,
                "to_department_id": self.destination.id,
                "note": NOTE,
                "change": {"field": "department", "from": self.scene.department.name, "to": self.destination.name},
            },
        )
        notification = NotificationOutbox.objects.get()
        self.assertEqual(notification.recipient, self.destination.poc_user)
        self.assertEqual(notification.source_activity, activity)
        self.assertEqual(notification.event_type, NotificationEventType.DEPARTMENT_CHANGED)

    def test_visibility_moves_to_the_new_poc_and_the_forwarding_poc_still_gets_the_response(self) -> None:
        response = self.change(self.scene.poc)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        detail_url = f"/api/v1/tickets/{self.ticket.id}/"
        self.client.force_authenticate(self.scene.poc)
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(self.destination.poc_user)
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_200_OK)
        for user in (self.scene.client_user, self.scene.facility_manager):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_200_OK)

    def test_the_old_poc_can_no_longer_act_on_the_forwarded_ticket(self) -> None:
        self.change(self.scene.poc)

        response = self.change(self.scene.poc, department_id=create_department().id)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_outside_the_visibility_scope_gets_404(self) -> None:
        self.assertEqual(self.change(self.destination.poc_user).status_code, status.HTTP_404_NOT_FOUND)
        self.assert_unchanged()

    def test_visible_users_who_are_not_the_current_poc_get_403(self) -> None:
        for user in (self.scene.client_user, self.scene.facility_manager):
            with self.subTest(role=user.role):
                self.assertEqual(self.change(user).status_code, status.HTTP_403_FORBIDDEN)
        self.assert_unchanged()

    def test_note_and_destination_are_validated(self) -> None:
        inactive = create_department()
        inactive.is_active = False
        inactive.save()
        cases = {
            "blank note": {"department_id": self.destination.id, "forwarding_note": "   "},
            "missing note": {"department_id": self.destination.id},
            "missing department": {"forwarding_note": NOTE},
            "unknown department": {"department_id": 999999, "forwarding_note": NOTE},
            "inactive department": {"department_id": inactive.id, "forwarding_note": NOTE},
            "current department": {"department_id": self.scene.department.id, "forwarding_note": NOTE},
        }
        self.client.force_authenticate(self.scene.poc)

        for name, payload in cases.items():
            with self.subTest(case=name):
                response = self.client.post(change_url(self.ticket.id), payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
        self.assert_unchanged()

    def test_ticket_with_an_assigned_worker_cannot_be_forwarded(self) -> None:
        move_to_assessment_stage(self.ticket, self.scene.worker)

        response = self.change(self.scene.poc)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["error"]["code"], "INVALID_TICKET_TRANSITION")
        self.assert_unchanged()

    def test_closed_ticket_cannot_be_forwarded(self) -> None:
        close_ticket(self.ticket, self.scene.client_user)

        self.assertEqual(self.change(self.scene.poc).status_code, status.HTTP_409_CONFLICT)
        self.assert_unchanged()

    def test_failure_after_the_department_is_updated_rolls_everything_back(self) -> None:
        with patch.object(services, "create_notifications", side_effect=RuntimeError("outbox unavailable")):
            with self.assertRaises(RuntimeError):
                services.change_department(
                    ticket_id=self.ticket.id,
                    actor=self.scene.poc,
                    department_id=self.destination.id,
                    forwarding_note=NOTE,
                )

        self.assert_unchanged()

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.notifications.models import NotificationOutbox
from apps.organizations.tests.helpers import create_department, create_user, map_user_to_client
from apps.tickets import services
from apps.tickets.models import (
    ActivityEventType,
    AssignmentEndReason,
    Ticket,
    TicketActivity,
    TicketAssessment,
    TicketAssignment,
    TicketStatus,
    WorkflowStage,
)
from apps.tickets.tests.helpers import (
    close_ticket,
    create_scene,
    move_to_assessment_stage,
    move_to_review_stage,
)


def resolve_url(ticket_id) -> str:
    return f"/api/v1/tickets/{ticket_id}/mark-resolved/"


class MarkResolvedTests(APITestCase):
    def setUp(self) -> None:
        self.scene = create_scene()
        self.ticket = self.scene.ticket

    def resolve(self, user, ticket_id=None):
        self.client.force_authenticate(user)
        return self.client.post(resolve_url(ticket_id or self.ticket.id))

    def assert_still_open(self) -> None:
        self.ticket.refresh_from_db()
        self.assertNotEqual(self.ticket.status, TicketStatus.CLOSED)
        self.assertIsNone(self.ticket.closed_by)
        self.assertFalse(TicketActivity.objects.filter(event_type=ActivityEventType.TICKET_RESOLVED).exists())

    def test_mapped_client_user_resolves_the_ticket_even_if_a_colleague_created_it(self) -> None:
        response = self.resolve(self.scene.colleague_client_user)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["ticket_id"], self.ticket.id)
        self.assertEqual(body["status"], "CLOSED")
        self.assertEqual(body["closed_by"]["id"], self.scene.colleague_client_user.id)
        self.assertIsNotNone(body["closed_at"])
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.CLOSED)
        self.assertEqual(self.ticket.closed_by, self.scene.colleague_client_user)
        self.assertIsNotNone(self.ticket.closed_at)

    def test_the_tickets_creator_can_resolve_it_whatever_their_role(self) -> None:
        for role in (UserRole.FACILITY_MANAGER, UserRole.DEPARTMENT_POC):
            with self.subTest(role=role):
                scene = create_scene()
                creator = scene.facility_manager if role == UserRole.FACILITY_MANAGER else create_department().poc_user
                scene.ticket.created_by = creator
                scene.ticket.save()

                response = self.resolve(creator, ticket_id=scene.ticket.id)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                scene.ticket.refresh_from_db()
                self.assertEqual(scene.ticket.closed_by, creator)

    def test_resolving_works_at_each_of_the_three_workflow_stages_and_keeps_the_stage(self) -> None:
        for stage in WorkflowStage.values:
            with self.subTest(stage=stage):
                scene = create_scene()
                if stage == WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT:
                    move_to_assessment_stage(scene.ticket, scene.worker)
                elif stage == WorkflowStage.PENDING_DEPARTMENT_POC_REVIEW:
                    move_to_review_stage(scene.ticket, scene.worker)

                response = self.resolve(scene.client_user, ticket_id=scene.ticket.id)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.json()["workflow_stage"], stage)
                self.assertEqual(Ticket.objects.get(pk=scene.ticket.id).workflow_stage, stage)

    def test_active_assignment_ends_but_assignment_and_assessment_history_survive(self) -> None:
        move_to_review_stage(self.ticket, self.scene.worker)

        self.resolve(self.scene.client_user)

        assignment = TicketAssignment.objects.get()
        self.assertIsNotNone(assignment.ended_at)
        self.assertEqual(assignment.end_reason, AssignmentEndReason.TICKET_CLOSED)
        self.assertEqual(TicketAssessment.objects.count(), 1)
        self.assertEqual(Ticket.objects.get().closed_at, assignment.ended_at)

    def test_resolution_is_recorded_with_the_previous_status_and_sends_no_notification(self) -> None:
        move_to_review_stage(self.ticket, self.scene.worker)

        self.resolve(self.scene.client_user)

        activity = TicketActivity.objects.get(event_type=ActivityEventType.TICKET_RESOLVED)
        self.assertEqual(activity.actor, self.scene.client_user)
        self.assertEqual(activity.metadata, {"change": {"field": "status", "from": "Technician Closed", "to": "Closed"}})
        self.assertFalse(NotificationOutbox.objects.exists())

    def test_open_ticket_is_recorded_as_changing_from_open(self) -> None:
        self.resolve(self.scene.client_user)

        activity = TicketActivity.objects.get()
        self.assertEqual(activity.metadata["change"]["from"], "Open")

    def test_the_ticket_moves_to_the_closed_tab(self) -> None:
        self.resolve(self.scene.client_user)

        self.client.force_authenticate(self.scene.client_user)
        closed = self.client.get("/api/v1/tickets/", {"tab": "closed"}).json()["results"]
        open_tab = self.client.get("/api/v1/tickets/", {"tab": "open"}).json()["results"]
        self.assertEqual([item["id"] for item in closed], [self.ticket.id])
        self.assertEqual(open_tab, [])

    def test_visible_users_who_are_neither_client_nor_creator_get_403(self) -> None:
        move_to_assessment_stage(self.ticket, self.scene.worker)
        for user in (self.scene.facility_manager, self.scene.poc, self.scene.worker):
            with self.subTest(role=user.role):
                response = self.resolve(user)

                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(response.json()["error"]["code"], "PERMISSION_DENIED")
        self.assert_still_open()

    def test_client_user_mapped_to_another_client_gets_404(self) -> None:
        other_client_user = create_scene().client_user

        response = self.resolve(other_client_user)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assert_still_open()

    def test_a_client_user_who_created_the_ticket_resolves_it_through_the_creator_rule(self) -> None:
        # Mapped to a different Client than the Ticket's, so only the creator rule applies.
        creator = create_user(UserRole.CLIENT)
        map_user_to_client(creator, create_scene().client)
        self.ticket.created_by = creator
        self.ticket.save()

        self.assertEqual(self.resolve(creator).status_code, status.HTTP_200_OK)

    def test_resolving_twice_is_a_409(self) -> None:
        self.resolve(self.scene.client_user)
        closed_at = Ticket.objects.get().closed_at

        response = self.resolve(self.scene.colleague_client_user)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["error"]["code"], "INVALID_TICKET_TRANSITION")
        ticket = Ticket.objects.get()
        self.assertEqual((ticket.closed_by, ticket.closed_at), (self.scene.client_user, closed_at))
        self.assertEqual(TicketActivity.objects.count(), 1)

    def test_closed_ticket_rejects_every_other_workflow_action(self) -> None:
        close_ticket(self.ticket, self.scene.client_user)
        other_department = create_department()

        self.client.force_authenticate(self.scene.poc)
        assign = self.client.post(
            f"/api/v1/tickets/{self.ticket.id}/assign-worker/", {"worker_id": self.scene.worker.id}, format="json"
        )
        forward = self.client.post(
            f"/api/v1/tickets/{self.ticket.id}/change-department/",
            {"department_id": other_department.id, "forwarding_note": "Please take this."},
            format="json",
        )

        self.assertEqual(assign.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(forward.status_code, status.HTTP_409_CONFLICT)

    def test_comments_are_still_allowed_after_closure(self) -> None:
        self.resolve(self.scene.client_user)

        self.client.force_authenticate(self.scene.facility_manager)
        response = self.client.post(f"/api/v1/tickets/{self.ticket.id}/comments/", {"body": "Thanks."}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_failure_while_recording_the_resolution_rolls_everything_back(self) -> None:
        move_to_review_stage(self.ticket, self.scene.worker)
        with patch.object(services, "record_activity", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                services.mark_ticket_resolved(ticket_id=self.ticket.id, actor=self.scene.client_user)

        self.assert_still_open()
        self.assertIsNone(TicketAssignment.objects.get().ended_at)

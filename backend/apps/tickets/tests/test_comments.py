from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.organizations.tests.helpers import create_department, create_worker
from apps.tickets.models import TicketActivity, TicketComment
from apps.tickets.tests.helpers import close_ticket, create_assignment, create_scene, move_to_assessment_stage


def comments_url(ticket_id) -> str:
    return f"/api/v1/tickets/{ticket_id}/comments/"


class AddCommentTests(APITestCase):
    def setUp(self) -> None:
        self.scene = create_scene()
        self.ticket = self.scene.ticket

    def comment(self, user, body="Technician inspected the AC.", ticket_id=None):
        self.client.force_authenticate(user)
        return self.client.post(comments_url(ticket_id or self.ticket.id), {"body": body}, format="json")

    def test_every_role_that_can_see_the_ticket_can_comment(self) -> None:
        move_to_assessment_stage(self.ticket, self.scene.worker)

        for user in (
            self.scene.client_user,
            self.scene.colleague_client_user,
            self.scene.facility_manager,
            self.scene.poc,
            self.scene.worker,
        ):
            with self.subTest(role=user.role):
                response = self.comment(user)

                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertEqual(TicketComment.objects.latest("id").author, user)

    def test_response_has_the_activity_item_shape(self) -> None:
        response = self.comment(self.scene.facility_manager, "  Please prioritise.  ")

        comment = TicketComment.objects.get()
        self.assertEqual(
            response.json(),
            {
                "id": f"comment-{comment.id}",
                "type": "COMMENT",
                "event_type": None,
                "actor": {
                    "id": self.scene.facility_manager.id,
                    "name": self.scene.facility_manager.name,
                    "role": "FACILITY_MANAGER",
                    "role_label": "Facility Manager",
                },
                "description": "Please prioritise.",
                "change": None,
                "note": None,
                "created_at": response.json()["created_at"],
            },
        )

    def test_a_historical_worker_and_a_user_after_closure_can_still_comment(self) -> None:
        create_assignment(
            self.ticket,
            self.scene.worker,
            ended_at=timezone.now(),
            end_reason="REASSIGNED",
        )
        close_ticket(self.ticket, self.scene.client_user)

        self.assertEqual(self.comment(self.scene.worker).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.comment(self.scene.client_user).status_code, status.HTTP_201_CREATED)

    def test_user_without_visibility_gets_404_and_nothing_is_written(self) -> None:
        for user in (create_scene().client_user, create_department().poc_user, create_worker(self.scene.department)):
            with self.subTest(role=user.role):
                self.assertEqual(self.comment(user).status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(TicketComment.objects.exists())

    def test_blank_missing_and_oversized_bodies_are_rejected(self) -> None:
        self.client.force_authenticate(self.scene.client_user)

        for payload in ({"body": ""}, {"body": "   \n "}, {}, {"body": "x" * 5001}):
            with self.subTest(payload=payload.get("body", "")[:10]):
                response = self.client.post(comments_url(self.ticket.id), payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("body", response.json()["error"]["details"])
        self.assertFalse(TicketComment.objects.exists())

    def test_a_comment_of_exactly_the_maximum_length_is_accepted(self) -> None:
        self.assertEqual(self.comment(self.scene.client_user, "x" * 5000).status_code, status.HTTP_201_CREATED)

    def test_commenting_does_not_add_an_activity_entry(self) -> None:
        self.comment(self.scene.client_user)

        self.assertFalse(TicketActivity.objects.exists())

    def test_unauthenticated_request_gets_401(self) -> None:
        response = self.client.post(comments_url(self.ticket.id), {"body": "Hi"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

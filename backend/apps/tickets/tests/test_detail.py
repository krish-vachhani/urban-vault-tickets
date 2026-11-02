from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.organizations.tests.helpers import create_department, create_user, create_worker
from apps.tickets.models import AssessmentOutcome
from apps.tickets.tests.helpers import (
    close_ticket,
    create_assignment,
    create_scene,
    move_to_assessment_stage,
    move_to_review_stage,
)


def detail_url(ticket_id) -> str:
    return f"/api/v1/tickets/{ticket_id}/"


class TicketDetailTests(APITestCase):
    def get_detail(self, user, ticket_id):
        self.client.force_authenticate(user)
        return self.client.get(detail_url(ticket_id))

    def test_authorized_roles_get_the_detail(self) -> None:
        scene = create_scene(description="AC is warm.")
        move_to_assessment_stage(scene.ticket, scene.worker)

        for user in (scene.client_user, scene.colleague_client_user, scene.facility_manager, scene.poc, scene.worker):
            with self.subTest(role=user.role):
                response = self.get_detail(user, scene.ticket.id)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.json()["id"], scene.ticket.id)

    def test_detail_shape(self) -> None:
        scene = create_scene(description="AC is warm.")
        move_to_review_stage(scene.ticket, scene.worker, AssessmentOutcome.PARTIALLY_RESOLVED)

        body = self.get_detail(scene.poc, scene.ticket.id).json()

        self.assertEqual(body["description"], "AC is warm.")
        self.assertEqual(body["origin_department"]["id"], scene.department.id)
        self.assertEqual(body["current_poc"]["id"], scene.poc.id)
        self.assertEqual(body["current_poc"]["role_label"], f"{scene.department.name} Manager")
        self.assertEqual(body["current_worker"]["id"], scene.worker.id)
        self.assertEqual(body["created_by"]["id"], scene.client_user.id)
        self.assertEqual(body["assessment"]["outcome"], "PARTIALLY_RESOLVED")
        self.assertEqual(body["assessment"]["submitted_by"]["id"], scene.worker.id)
        self.assertIsNone(body["closed_by"])
        self.assertIsNone(body["closed_at"])
        self.assertTrue(body["action_required"])

    def test_unassigned_ticket_has_no_worker_and_no_assessment(self) -> None:
        scene = create_scene()

        body = self.get_detail(scene.client_user, scene.ticket.id).json()

        self.assertIsNone(body["current_worker"])
        self.assertIsNone(body["assessment"])

    def test_closed_ticket_reports_who_closed_it_and_has_no_current_worker(self) -> None:
        scene = create_scene()
        move_to_review_stage(scene.ticket, scene.worker)
        close_ticket(scene.ticket, scene.client_user)

        body = self.get_detail(scene.client_user, scene.ticket.id).json()

        self.assertEqual(body["closed_by"]["id"], scene.client_user.id)
        self.assertIsNotNone(body["closed_at"])
        self.assertIsNone(body["current_worker"])
        self.assertEqual(body["workflow_stage"], "PENDING_DEPARTMENT_POC_REVIEW")
        self.assertIsNotNone(body["assessment"])

    def test_user_outside_the_visibility_scope_gets_404_like_an_unknown_ticket(self) -> None:
        scene = create_scene()
        outsiders = (
            create_scene().client_user,
            create_scene().facility_manager,
            create_department().poc_user,
            create_worker(scene.department),
        )

        unknown = self.get_detail(scene.client_user, 999999)
        for outsider in outsiders:
            with self.subTest(role=outsider.role):
                response = self.get_detail(outsider, scene.ticket.id)

                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
                self.assertEqual(response.json(), unknown.json())

    def test_malformed_ticket_id_is_a_validation_error(self) -> None:
        response = self.get_detail(create_user(UserRole.CLIENT), "abc")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request_gets_401(self) -> None:
        scene = create_scene()

        self.assertEqual(self.client.get(detail_url(scene.ticket.id)).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_there_is_no_generic_update_or_delete(self) -> None:
        scene = create_scene()
        self.client.force_authenticate(scene.poc)

        for method in (self.client.put, self.client.patch, self.client.delete):
            with self.subTest(method=method.__name__):
                response = method(detail_url(scene.ticket.id), {"status": "CLOSED"}, format="json")

                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        scene.ticket.refresh_from_db()
        self.assertEqual(scene.ticket.status, "OPEN")

    def test_options_requests_get_a_405_envelope_not_a_server_error(self) -> None:
        scene = create_scene()
        self.client.force_authenticate(scene.poc)

        for url in ("/api/v1/tickets/", detail_url(scene.ticket.id), f"{detail_url(scene.ticket.id)}assign-worker/"):
            with self.subTest(url=url):
                response = self.client.options(url)

                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
                self.assertEqual(response.json()["error"]["code"], "METHOD_NOT_ALLOWED")

    def test_detail_query_count_is_fixed(self) -> None:
        scene = create_scene()
        move_to_review_stage(scene.ticket, scene.worker)
        with CaptureQueriesContext(connection) as queries:
            self.get_detail(scene.poc, scene.ticket.id)

        self.assertLessEqual(len(queries), 12)


class AvailableActionsTests(APITestCase):
    def available_actions(self, user, ticket) -> dict[str, bool]:
        self.client.force_authenticate(user)
        return self.client.get(detail_url(ticket.id)).json()["available_actions"]

    def test_current_poc_can_assign_and_forward_only_while_awaiting_assignment(self) -> None:
        scene = create_scene()

        before = self.available_actions(scene.poc, scene.ticket)
        move_to_assessment_stage(scene.ticket, scene.worker)
        after = self.available_actions(scene.poc, scene.ticket)

        self.assertTrue(before["can_assign_worker"] and before["can_change_department"])
        self.assertFalse(after["can_assign_worker"] or after["can_change_department"])
        self.assertFalse(before["can_submit_assessment"] or before["can_mark_resolved"])

    def test_only_the_active_worker_can_submit_and_only_at_the_assessment_stage(self) -> None:
        scene = create_scene()
        historical_worker = create_worker(scene.department)
        create_assignment(
            scene.ticket, historical_worker, ended_at=scene.ticket.created_at, end_reason="REASSIGNED"
        )
        move_to_assessment_stage(scene.ticket, scene.worker)

        self.assertTrue(self.available_actions(scene.worker, scene.ticket)["can_submit_assessment"])
        self.assertFalse(self.available_actions(historical_worker, scene.ticket)["can_submit_assessment"])

        scene.ticket.workflow_stage = "PENDING_DEPARTMENT_POC_REVIEW"
        scene.ticket.status = "TECHNICIAN_CLOSED"
        scene.ticket.save()
        self.assertFalse(self.available_actions(scene.worker, scene.ticket)["can_submit_assessment"])

    def test_mark_resolved_is_for_mapped_client_users_and_the_creator_while_not_closed(self) -> None:
        scene = create_scene()
        creator_manager_ticket = create_scene(created_by=create_scene().facility_manager)

        self.assertTrue(self.available_actions(scene.client_user, scene.ticket)["can_mark_resolved"])
        self.assertTrue(self.available_actions(scene.colleague_client_user, scene.ticket)["can_mark_resolved"])
        self.assertFalse(self.available_actions(scene.facility_manager, scene.ticket)["can_mark_resolved"])
        self.assertFalse(self.available_actions(scene.poc, scene.ticket)["can_mark_resolved"])
        self.assertTrue(
            self.available_actions(creator_manager_ticket.ticket.created_by, creator_manager_ticket.ticket)[
                "can_mark_resolved"
            ]
        )

        close_ticket(scene.ticket, scene.client_user)
        self.assertFalse(self.available_actions(scene.client_user, scene.ticket)["can_mark_resolved"])

    def test_everyone_who_can_see_the_ticket_can_comment(self) -> None:
        scene = create_scene()
        move_to_assessment_stage(scene.ticket, scene.worker)
        close_ticket(scene.ticket, scene.client_user)

        for user in (scene.client_user, scene.facility_manager, scene.poc, scene.worker):
            with self.subTest(role=user.role):
                self.assertTrue(self.available_actions(user, scene.ticket)["can_comment"])

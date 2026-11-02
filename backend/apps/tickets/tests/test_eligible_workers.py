from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.organizations.models import DepartmentWorker
from apps.organizations.tests.helpers import create_department, create_user, create_worker
from apps.tickets.models import TicketStatus, WorkflowStage
from apps.tickets.tests.helpers import create_ticket


class EligibleWorkersTests(APITestCase):
    def setUp(self) -> None:
        self.department = create_department()
        self.poc = self.department.poc_user
        self.ticket = create_ticket(origin_department=self.department)

    def get_eligible_workers(self, user=None):
        self.client.force_authenticate(user or self.poc)
        return self.client.get(f"/api/v1/tickets/{self.ticket.id}/eligible-workers/")

    def test_current_poc_gets_active_workers_of_the_current_department(self) -> None:
        worker = create_worker(self.department)
        create_worker(create_department())  # a Worker in another Department
        inactive_worker = create_worker(self.department)
        inactive_worker.is_active = False
        inactive_worker.save()

        response = self.get_eligible_workers()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"results": [{"id": worker.id, "name": worker.name, "role": "WORKER", "role_label": "Technician"}]})

    def test_forwarded_ticket_lists_the_new_departments_workers_to_the_new_poc(self) -> None:
        new_department = create_department()
        new_worker = create_worker(new_department)
        create_worker(self.department)
        self.ticket.current_department = new_department
        self.ticket.save()

        response = self.get_eligible_workers(new_department.poc_user)

        self.assertEqual([worker["id"] for worker in response.json()["results"]], [new_worker.id])

    def test_user_who_cannot_see_the_ticket_gets_404(self) -> None:
        for user in (create_department().poc_user, create_user(UserRole.CLIENT), create_user(UserRole.FACILITY_MANAGER)):
            with self.subTest(role=user.role):
                response = self.get_eligible_workers(user)

                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
                self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_unknown_ticket_gets_the_same_404_as_an_invisible_one(self) -> None:
        self.client.force_authenticate(create_department().poc_user)
        unknown = self.client.get("/api/v1/tickets/999999/eligible-workers/")
        invisible = self.get_eligible_workers(create_department().poc_user)

        self.assertEqual(unknown.json(), invisible.json())

    def test_visible_user_who_is_not_the_current_poc_gets_403(self) -> None:
        # The creator keeps visibility after routing, but is not the Department POC.
        other_poc = create_department().poc_user
        self.ticket.created_by = other_poc
        self.ticket.save()

        response = self.get_eligible_workers(other_poc)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["error"]["code"], "PERMISSION_DENIED")

    def test_ticket_creator_who_is_a_client_gets_403(self) -> None:
        client_user = self.ticket.created_by

        response = self.get_eligible_workers(client_user)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ticket_not_awaiting_assignment_gets_409(self) -> None:
        self.ticket.workflow_stage = WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT
        self.ticket.save()

        response = self.get_eligible_workers()

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["error"]["code"], "INVALID_TICKET_TRANSITION")

    def test_closed_ticket_gets_409(self) -> None:
        self.ticket.status = TicketStatus.CLOSED
        self.ticket.closed_by = self.ticket.created_by
        self.ticket.closed_at = self.ticket.created_at
        self.ticket.save()

        self.assertEqual(self.get_eligible_workers().status_code, status.HTTP_409_CONFLICT)

    def test_department_without_workers_returns_an_empty_result(self) -> None:
        self.assertEqual(self.get_eligible_workers().json(), {"results": []})
        self.assertFalse(DepartmentWorker.objects.exists())

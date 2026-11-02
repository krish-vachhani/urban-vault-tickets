from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.notifications.models import NotificationOutbox
from apps.organizations.tests.helpers import (
    create_client,
    create_department,
    create_issue,
    create_office,
    create_property,
    create_user,
    create_worker,
    map_user_to_client,
)


class FullTicketWorkflowTest(APITestCase):
    """The whole documented journey, driven only through the HTTP API."""

    def test_client_creates_poc_assigns_worker_assesses_client_resolves(self) -> None:
        manager = create_user(UserRole.FACILITY_MANAGER)
        client_record = create_client()
        office = create_office(client_record, create_property(manager))
        client_user = create_user(UserRole.CLIENT)
        map_user_to_client(client_user, client_record)
        department = create_department()
        worker = create_worker(department)
        issue = create_issue(department)

        self.client.force_authenticate(client_user)
        created = self.client.post(
            "/api/v1/tickets/", {"client_office_id": office.id, "issue_ids": [issue.id]}, format="json"
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        ticket_url = f"/api/v1/tickets/{created.json()['id']}"

        self.client.force_authenticate(department.poc_user)
        eligible = self.client.get(f"{ticket_url}/eligible-workers/")
        self.assertEqual([item["id"] for item in eligible.json()["results"]], [worker.id])
        assigned = self.client.post(f"{ticket_url}/assign-worker/", {"worker_id": worker.id}, format="json")
        self.assertEqual(assigned.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(worker)
        self.assertEqual(self.client.get(f"{ticket_url}/").json()["action_required"], True)
        assessed = self.client.post(f"{ticket_url}/submit-assessment/", {"outcome": "PARTIALLY_RESOLVED"}, format="json")
        self.assertEqual(assessed.status_code, status.HTTP_201_CREATED)
        comment = self.client.post(f"{ticket_url}/comments/", {"body": "Left a note."}, format="json")
        self.assertEqual(comment.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(client_user)
        resolved = self.client.post(f"{ticket_url}/mark-resolved/")
        self.assertEqual(resolved.status_code, status.HTTP_200_OK)

        detail = self.client.get(f"{ticket_url}/").json()
        self.assertEqual((detail["status"], detail["workflow_stage"]), ("CLOSED", "PENDING_DEPARTMENT_POC_REVIEW"))
        self.assertIsNone(detail["current_worker"])
        feed = self.client.get(f"{ticket_url}/activities/").json()
        self.assertEqual(
            [item["event_type"] for item in feed["results"]],
            [
                "TICKET_CREATED",
                "TICKET_ROUTED",
                "WORKER_ASSIGNED",
                "ASSESSMENT_SUBMITTED",
                None,
                "TICKET_RESOLVED",
            ],
        )
        # Creation notified the Facility Manager and the POC; assignment the Worker; assessment the POC.
        self.assertEqual(NotificationOutbox.objects.count(), 4)
        self.assertEqual(self.client.get("/api/v1/tickets/", {"tab": "closed"}).json()["count"], 1)

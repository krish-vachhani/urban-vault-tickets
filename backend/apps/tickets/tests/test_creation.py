from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.notifications.models import NotificationEventType, NotificationOutbox, OutboxStatus
from apps.organizations.tests.helpers import (
    create_client,
    create_department,
    create_floor,
    create_issue,
    create_office,
    create_property,
    create_user,
    map_floor_to_office,
    map_user_to_client,
)
from apps.tickets import services
from apps.tickets.models import (
    ActivityEventType,
    Ticket,
    TicketActivity,
    TicketFloor,
    TicketIssue,
    TicketStatus,
    WorkflowStage,
)

TICKETS_URL = "/api/v1/tickets/"


class TicketCreationTestCase(APITestCase):
    """A Client, an Office in a managed Property, one Floor-less Office, and a Technical Issue."""

    def setUp(self) -> None:
        self.facility_manager = create_user(UserRole.FACILITY_MANAGER)
        self.property_record = create_property(self.facility_manager)
        self.client_record = create_client()
        self.office = create_office(self.client_record, self.property_record)
        self.client_user = create_user(UserRole.CLIENT)
        map_user_to_client(self.client_user, self.client_record)
        self.department = create_department()
        self.issue = create_issue(self.department)

    def post_ticket(self, user, **overrides):
        payload = {"client_office_id": self.office.id, "issue_ids": [self.issue.id], **overrides}
        self.client.force_authenticate(user)
        return self.client.post(TICKETS_URL, payload, format="json")

    def assert_nothing_created(self) -> None:
        for model in (Ticket, TicketIssue, TicketFloor, TicketActivity, NotificationOutbox):
            self.assertFalse(model.objects.exists(), f"{model.__name__} rows were left behind")


class SuccessfulCreationTests(TicketCreationTestCase):
    def test_client_creates_a_ticket_with_server_derived_fields(self) -> None:
        response = self.post_ticket(self.client_user, description="AC is warm.")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        ticket = Ticket.objects.get()
        self.assertEqual(body["id"], ticket.id)
        self.assertEqual(body["ticket_number"], f"TKT-{ticket.id}")
        self.assertEqual(body["workflow_stage"], WorkflowStage.PENDING_TECHNICIAN_ASSIGNMENT)
        self.assertEqual(body["status"], TicketStatus.OPEN)
        self.assertEqual(body["description"], "AC is warm.")
        self.assertEqual(body["origin_department"], {"id": self.department.id, "name": self.department.name})
        self.assertEqual(body["current_department"], body["origin_department"])
        self.assertEqual(body["client_office"], {"id": self.office.id, "name": self.office.name})
        self.assertEqual(body["issues"], [{"id": self.issue.id, "name": self.issue.name}])
        self.assertEqual(ticket.created_by, self.client_user)
        self.assertEqual(ticket.origin_department, self.department)
        self.assertEqual(ticket.current_department, self.department)
        self.assertIsNone(ticket.closed_by)

    def test_creation_records_a_creator_activity_and_a_system_routing_activity(self) -> None:
        self.post_ticket(self.client_user)

        created, routed = TicketActivity.objects.order_by("id")
        self.assertEqual((created.event_type, created.actor), (ActivityEventType.TICKET_CREATED, self.client_user))
        self.assertEqual((routed.event_type, routed.actor), (ActivityEventType.TICKET_ROUTED, None))
        self.assertEqual(routed.metadata, {"department_id": self.department.id})

    def test_creation_queues_notifications_for_the_facility_manager_and_department_poc(self) -> None:
        self.post_ticket(self.client_user)

        routed = TicketActivity.objects.get(event_type=ActivityEventType.TICKET_ROUTED)
        outbox_rows = NotificationOutbox.objects.all()
        self.assertEqual(
            {row.recipient_id for row in outbox_rows}, {self.facility_manager.id, self.department.poc_user_id}
        )
        for row in outbox_rows:
            self.assertEqual(row.source_activity, routed)
            self.assertEqual(row.event_type, NotificationEventType.TICKET_ROUTED)
            self.assertEqual(row.status, OutboxStatus.PENDING)
            self.assertEqual(row.idempotency_key, f"activity:{routed.id}:recipient:{row.recipient_id}")

    def test_client_description_is_optional_and_blank_is_stored_as_none(self) -> None:
        for description in (None, "", "   "):
            with self.subTest(description=description):
                payload = {} if description is None else {"description": description}

                response = self.post_ticket(self.client_user, **payload)

                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertIsNone(Ticket.objects.get(pk=response.json()["id"]).description)

    def test_multiple_issues_of_one_department_are_attached(self) -> None:
        second_issue = create_issue(self.department)

        response = self.post_ticket(self.client_user, issue_ids=[self.issue.id, second_issue.id])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TicketIssue.objects.count(), 2)

    def test_request_cannot_set_server_derived_fields(self) -> None:
        other_department = create_department()
        response = self.post_ticket(
            self.client_user,
            created_by_id=create_user(UserRole.CLIENT).id,
            origin_department_id=other_department.id,
            current_department_id=other_department.id,
            workflow_stage=WorkflowStage.PENDING_DEPARTMENT_POC_REVIEW,
            status=TicketStatus.CLOSED,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ticket = Ticket.objects.get()
        self.assertEqual(ticket.created_by, self.client_user)
        self.assertEqual(ticket.origin_department, self.department)
        self.assertEqual(ticket.workflow_stage, WorkflowStage.PENDING_TECHNICIAN_ASSIGNMENT)
        self.assertEqual(ticket.status, TicketStatus.OPEN)

    def test_department_poc_creator_can_still_open_a_ticket_routed_to_another_department(self) -> None:
        other_poc = create_department().poc_user
        map_user_to_client(other_poc, self.client_record)

        response = self.post_ticket(other_poc, description="Needs fixing.")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        detail = self.client.get(f"{TICKETS_URL}{response.json()['id']}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertTrue(detail.json()["available_actions"]["can_mark_resolved"])


class CreationAuthorizationTests(TicketCreationTestCase):
    def test_unauthenticated_request_gets_401(self) -> None:
        response = self.client.post(TICKETS_URL, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_worker_gets_403_before_the_body_is_validated(self) -> None:
        worker = create_user(UserRole.WORKER)
        self.client.force_authenticate(worker)

        response = self.client.post(TICKETS_URL, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["error"]["code"], "PERMISSION_DENIED")
        self.assert_nothing_created()

    def test_facility_manager_creates_only_in_a_property_they_manage(self) -> None:
        map_user_to_client(self.facility_manager, self.client_record)
        other_manager = create_user(UserRole.FACILITY_MANAGER)
        map_user_to_client(other_manager, self.client_record)

        allowed = self.post_ticket(self.facility_manager, description="Leak.")
        denied = self.post_ticket(other_manager, description="Leak.")

        self.assertEqual(allowed.status_code, status.HTTP_201_CREATED)
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("client_office_id", denied.json()["error"]["details"])
        self.assertEqual(Ticket.objects.count(), 1)

    def test_department_poc_creates_for_any_office_of_a_mapped_client_in_any_property(self) -> None:
        poc = create_department().poc_user
        map_user_to_client(poc, self.client_record)
        office_in_unrelated_property = create_office(self.client_record, create_property())

        response = self.post_ticket(poc, client_office_id=office_in_unrelated_property.id, description="Noise.")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_unmapped_office_and_unknown_office_get_the_same_400(self) -> None:
        unrelated_office = create_office()

        unmapped = self.post_ticket(self.client_user, client_office_id=unrelated_office.id)
        unknown = self.post_ticket(self.client_user, client_office_id=999999)

        self.assertEqual(unmapped.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(unmapped.json(), unknown.json())
        self.assert_nothing_created()

    def test_inactive_office_is_rejected(self) -> None:
        self.office.is_active = False
        self.office.save()

        response = self.post_ticket(self.client_user)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_internal_employees_must_provide_a_description(self) -> None:
        map_user_to_client(self.facility_manager, self.client_record)
        poc = create_department().poc_user
        map_user_to_client(poc, self.client_record)

        for user in (self.facility_manager, poc):
            for payload in ({}, {"description": ""}, {"description": "   "}):
                with self.subTest(role=user.role, payload=payload):
                    response = self.post_ticket(user, **payload)

                    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                    self.assertIn("description", response.json()["error"]["details"])
        self.assert_nothing_created()


class IssueValidationTests(TicketCreationTestCase):
    def test_issues_from_different_departments_are_rejected(self) -> None:
        other_department_issue = create_issue()

        response = self.post_ticket(self.client_user, issue_ids=[self.issue.id, other_department_issue.id])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("issue_ids", response.json()["error"]["details"])
        self.assert_nothing_created()

    def test_missing_empty_duplicate_unknown_and_inactive_issues_are_rejected(self) -> None:
        inactive_issue = create_issue(self.department)
        inactive_issue.is_active = False
        inactive_issue.save()
        cases = {
            "empty": [],
            "duplicate": [self.issue.id, self.issue.id],
            "unknown": [999999],
            "inactive": [inactive_issue.id],
            "not numbers": ["abc"],
        }

        for name, issue_ids in cases.items():
            with self.subTest(case=name):
                response = self.post_ticket(self.client_user, issue_ids=issue_ids)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("issue_ids", response.json()["error"]["details"])
        self.assert_nothing_created()

    def test_missing_issue_ids_is_rejected(self) -> None:
        self.client.force_authenticate(self.client_user)

        response = self.client.post(TICKETS_URL, {"client_office_id": self.office.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("issue_ids", response.json()["error"]["details"])


class FloorValidationTests(TicketCreationTestCase):
    def test_office_without_mapped_floors_creates_no_floor_rows_and_rejects_submitted_ones(self) -> None:
        stray_floor = create_floor(self.property_record)

        accepted = self.post_ticket(self.client_user)
        rejected = self.post_ticket(self.client_user, floor_ids=[stray_floor.id])

        self.assertEqual(accepted.status_code, status.HTTP_201_CREATED)
        self.assertFalse(TicketFloor.objects.exists())
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("floor_ids", rejected.json()["error"]["details"])

    def test_office_with_one_mapped_floor_attaches_it_automatically(self) -> None:
        only_floor = create_floor(self.property_record)
        map_floor_to_office(only_floor, self.office)

        response = self.post_ticket(self.client_user)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["floors"], [{"id": only_floor.id, "name": only_floor.name}])

    def test_office_with_several_floors_requires_a_selection_from_its_own_floors(self) -> None:
        first_floor, second_floor = create_floor(self.property_record), create_floor(self.property_record)
        map_floor_to_office(first_floor, self.office)
        map_floor_to_office(second_floor, self.office)
        unmapped_floor = create_floor(self.property_record)
        foreign_floor = create_floor()

        for name, floor_ids in {
            "missing": [],
            "unmapped": [unmapped_floor.id],
            "other property": [foreign_floor.id],
            "unknown": [999999],
            "duplicate": [first_floor.id, first_floor.id],
        }.items():
            with self.subTest(case=name):
                response = self.post_ticket(self.client_user, floor_ids=floor_ids)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("floor_ids", response.json()["error"]["details"])
        self.assert_nothing_created()

        accepted = self.post_ticket(self.client_user, floor_ids=[second_floor.id])
        self.assertEqual(accepted.status_code, status.HTTP_201_CREATED)
        self.assertEqual([floor["id"] for floor in accepted.json()["floors"]], [second_floor.id])


class CreationTransactionTests(TicketCreationTestCase):
    def test_failure_while_queueing_notifications_rolls_back_every_write(self) -> None:
        with patch.object(services, "create_notifications", side_effect=RuntimeError("outbox unavailable")):
            with self.assertRaises(RuntimeError):
                services.create_ticket(
                    creator=self.client_user,
                    client_office_id=self.office.id,
                    issue_ids=[self.issue.id],
                    floor_ids=[],
                    description=None,
                )

        self.assert_nothing_created()

    def test_unexpected_failure_over_http_is_a_500_envelope_and_leaves_nothing_behind(self) -> None:
        with patch.object(services, "create_notifications", side_effect=RuntimeError("outbox unavailable")):
            with self.assertLogs("config.exception_handler", level="ERROR"):
                response = self.post_ticket(self.client_user)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json()["error"]["code"], "INTERNAL_ERROR")
        self.assert_nothing_created()

    def test_creator_who_is_also_the_recipient_is_not_notified(self) -> None:
        poc = self.department.poc_user
        map_user_to_client(poc, self.client_record)

        self.post_ticket(poc, description="Lights flicker.")

        self.assertEqual(
            list(NotificationOutbox.objects.values_list("recipient_id", flat=True)), [self.facility_manager.id]
        )

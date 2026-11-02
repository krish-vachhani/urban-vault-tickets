from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.organizations.models import Issue
from apps.organizations.tests.helpers import (
    create_client,
    create_department,
    create_floor,
    create_office,
    create_property,
    create_user,
    create_worker,
    map_floor_to_office,
)
from apps.tickets.models import TicketIssue, WorkflowStage
from apps.tickets.tests.helpers import (
    close_ticket,
    create_assignment,
    create_client_user,
    create_scene,
    create_ticket,
    move_to_assessment_stage,
    move_to_review_stage,
)

LIST_URL = "/api/v1/tickets/"


def add_issue(ticket, name: str) -> None:
    issue, _ = Issue.objects.get_or_create(department=ticket.origin_department, name=name)
    TicketIssue.objects.create(ticket=ticket, issue=issue)


class ListingTestCase(APITestCase):
    def list_tickets(self, user, **query):
        self.client.force_authenticate(user)
        return self.client.get(LIST_URL, query)

    def listed_ids(self, user, **query) -> list[int]:
        response = self.list_tickets(user, **query)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return [ticket["id"] for ticket in response.json()["results"]]


class RoleScopeTests(ListingTestCase):
    def test_each_role_lists_only_its_own_tickets(self) -> None:
        scene = create_scene()
        unrelated = create_scene()
        move_to_assessment_stage(scene.ticket, scene.worker)

        for name, user in {
            "client": scene.client_user,
            "colleague client": scene.colleague_client_user,
            "facility manager": scene.facility_manager,
            "department poc": scene.poc,
            "worker": scene.worker,
        }.items():
            with self.subTest(role=name):
                self.assertEqual(self.listed_ids(user), [scene.ticket.id])
        self.assertEqual(self.listed_ids(unrelated.client_user), [unrelated.ticket.id])

    def test_a_user_sees_the_tickets_they_created_even_when_no_role_rule_applies(self) -> None:
        scene = create_scene()
        other_department = create_department()
        created_by_poc = create_ticket(
            client_office=scene.office, origin_department=other_department, created_by=scene.poc
        )
        # Routed to another Department, so the creator no longer matches the "current Department" rule.
        created_by_poc.current_department = other_department
        created_by_poc.save()

        self.assertIn(created_by_poc.id, self.listed_ids(scene.poc))

    def test_worker_with_several_assignments_on_a_ticket_sees_it_once(self) -> None:
        scene = create_scene()
        create_assignment(scene.ticket, scene.worker, ended_at=timezone.now(), end_reason="REASSIGNED")
        move_to_assessment_stage(scene.ticket, scene.worker)

        response = self.list_tickets(scene.worker)

        self.assertEqual(response.json()["count"], 1)

    def test_unauthenticated_request_gets_401(self) -> None:
        self.assertEqual(self.client.get(LIST_URL).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filters_cannot_widen_the_users_scope(self) -> None:
        scene = create_scene()
        other = create_scene()

        ids = self.listed_ids(
            scene.client_user,
            client_id=other.client.id,
            department_id=other.department.id,
            facility_manager_id=other.facility_manager.id,
        )

        self.assertEqual(ids, [])


class TabTests(ListingTestCase):
    def test_open_tab_holds_open_and_technician_closed_and_closed_tab_only_closed(self) -> None:
        scene = create_scene()
        open_ticket = scene.ticket
        technician_closed = create_ticket(client_office=scene.office, origin_department=scene.department)
        move_to_review_stage(technician_closed, scene.worker)
        closed = create_ticket(client_office=scene.office, origin_department=scene.department)
        close_ticket(closed, scene.client_user)

        self.assertEqual(
            set(self.listed_ids(scene.client_user)), {open_ticket.id, technician_closed.id}, "default tab is open"
        )
        self.assertEqual(set(self.listed_ids(scene.client_user, tab="open")), {open_ticket.id, technician_closed.id})
        self.assertEqual(self.listed_ids(scene.client_user, tab="closed"), [closed.id])

    def test_workflow_stage_filter_applies_to_the_closed_tab_too(self) -> None:
        scene = create_scene()
        resolved_in_review = create_ticket(client_office=scene.office, origin_department=scene.department)
        move_to_review_stage(resolved_in_review, scene.worker)
        close_ticket(resolved_in_review, scene.client_user)

        ids = self.listed_ids(
            scene.client_user, tab="closed", workflow_stage=WorkflowStage.PENDING_DEPARTMENT_POC_REVIEW
        )

        self.assertEqual(ids, [resolved_in_review.id])


class FilterTests(ListingTestCase):
    def setUp(self) -> None:
        # One Facility Manager sees tickets of two Clients, in two Departments, at different stages.
        self.manager = create_user(UserRole.FACILITY_MANAGER)
        self.property_record = create_property(self.manager)
        self.first_client, self.second_client = create_client(), create_client()
        self.first_department, self.second_department = create_department(), create_department()
        self.first_ticket = create_ticket(
            client_office=create_office(self.first_client, self.property_record),
            origin_department=self.first_department,
        )
        self.second_ticket = create_ticket(
            client_office=create_office(self.second_client, self.property_record),
            origin_department=self.second_department,
            workflow_stage=WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT,
        )

    def test_client_filter(self) -> None:
        self.assertEqual(self.listed_ids(self.manager, client_id=self.second_client.id), [self.second_ticket.id])

    def test_department_filter_uses_the_current_department_not_the_origin(self) -> None:
        self.first_ticket.current_department = self.second_department
        self.first_ticket.save()

        self.assertEqual(
            set(self.listed_ids(self.manager, department_id=self.second_department.id)),
            {self.first_ticket.id, self.second_ticket.id},
        )
        self.assertEqual(self.listed_ids(self.manager, department_id=self.first_department.id), [])

    def test_facility_manager_filter_narrows_what_a_client_already_sees(self) -> None:
        other_property = create_property()
        client_user = create_client_user(self.first_client)
        in_other_property = create_ticket(
            client_office=create_office(self.first_client, other_property), origin_department=self.first_department
        )

        self.assertEqual(
            self.listed_ids(client_user, facility_manager_id=other_property.facility_manager_id),
            [in_other_property.id],
        )
        self.assertEqual(self.listed_ids(client_user, facility_manager_id=self.manager.id), [self.first_ticket.id])

    def test_workflow_stage_filter(self) -> None:
        ids = self.listed_ids(self.manager, workflow_stage=WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT)

        self.assertEqual(ids, [self.second_ticket.id])

    def test_filters_combine(self) -> None:
        ids = self.listed_ids(
            self.manager,
            client_id=self.second_client.id,
            department_id=self.second_department.id,
            facility_manager_id=self.manager.id,
            workflow_stage=WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT,
        )
        mismatch = self.listed_ids(
            self.manager,
            client_id=self.first_client.id,
            workflow_stage=WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT,
        )

        self.assertEqual(ids, [self.second_ticket.id])
        self.assertEqual(mismatch, [])

    def test_unknown_but_well_formed_ids_return_an_empty_result(self) -> None:
        for parameter in ("client_id", "department_id", "facility_manager_id"):
            with self.subTest(parameter=parameter):
                self.assertEqual(self.listed_ids(self.manager, **{parameter: 999999}), [])

    def test_malformed_and_unsupported_values_are_validation_errors(self) -> None:
        bad_queries = [
            ("client_id", "abc"),
            ("department_id", "0"),
            ("facility_manager_id", "-1"),
            ("tab", "archived"),
            ("ordering", "name"),
            ("workflow_stage", "DONE"),
            ("page", "0"),
            ("page_size", "0"),
            ("page_size", "51"),
        ]
        for parameter, value in bad_queries:
            with self.subTest(parameter=parameter, value=value):
                response = self.list_tickets(self.manager, **{parameter: value})

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
                self.assertIn(parameter, response.json()["error"]["details"])

    def test_page_size_500_and_non_numeric_page_are_rejected(self) -> None:
        for query in ({"page_size": 500}, {"page": "last"}, {"page": "abc"}, {"page": 99}):
            with self.subTest(query=query):
                self.assertEqual(self.list_tickets(self.manager, **query).status_code, status.HTTP_400_BAD_REQUEST)


class SearchTests(ListingTestCase):
    def setUp(self) -> None:
        self.scene = create_scene()
        self.ac_ticket = self.scene.ticket
        add_issue(self.ac_ticket, "AC not cooling")
        add_issue(self.ac_ticket, "AC making noise")
        self.internet_ticket = create_ticket(client_office=self.scene.office, origin_department=self.scene.department)
        add_issue(self.internet_ticket, "Internet not working")

    def test_search_is_case_insensitive_and_partial(self) -> None:
        for text in ("ac", "AC NOT", "ooling", "internet"):
            with self.subTest(text=text):
                expected = self.internet_ticket.id if text == "internet" else self.ac_ticket.id
                self.assertEqual(self.listed_ids(self.scene.client_user, search=text), [expected])

    def test_a_ticket_with_several_matching_issues_is_listed_once(self) -> None:
        response = self.list_tickets(self.scene.client_user, search="AC")

        self.assertEqual(response.json()["count"], 1)

    def test_search_covers_issue_names_only(self) -> None:
        self.ac_ticket.description = "The printer is jammed"
        self.ac_ticket.save()

        self.assertEqual(self.listed_ids(self.scene.client_user, search="printer"), [])
        self.assertEqual(self.listed_ids(self.scene.client_user, search=self.scene.client.name), [])

    def test_blank_search_does_not_filter(self) -> None:
        self.assertEqual(len(self.listed_ids(self.scene.client_user, search="  ")), 2)


class OrderingAndPaginationTests(ListingTestCase):
    def setUp(self) -> None:
        self.scene = create_scene()
        base_time = timezone.now() - timedelta(days=10)
        self.scene.ticket.delete()
        self.tickets = [
            create_ticket(
                client_office=self.scene.office,
                origin_department=self.scene.department,
                created_by=self.scene.client_user,
                created_at=base_time + timedelta(hours=hour),
            )
            for hour in range(25)
        ]

    def test_newest_first_is_the_default_and_oldest_first_reverses_it(self) -> None:
        newest_first = [ticket.id for ticket in reversed(self.tickets)][:10]

        self.assertEqual(self.listed_ids(self.scene.client_user), newest_first)
        self.assertEqual(self.listed_ids(self.scene.client_user, ordering="-created_at"), newest_first)
        self.assertEqual(
            self.listed_ids(self.scene.client_user, ordering="created_at"),
            [ticket.id for ticket in self.tickets][:10],
        )

    def test_tickets_with_the_same_timestamp_are_ordered_by_id(self) -> None:
        same_time = timezone.now()
        twins = [
            create_ticket(
                client_office=self.scene.office, origin_department=self.scene.department, created_at=same_time
            )
            for _ in range(3)
        ]
        ids = [ticket.id for ticket in twins]

        newest = self.listed_ids(self.scene.client_user, ordering="-created_at")[:3]
        oldest = self.listed_ids(self.scene.client_user, ordering="created_at", page_size=50)[-3:]

        self.assertEqual(newest, sorted(ids, reverse=True))
        self.assertEqual(oldest, sorted(ids))

    def test_pages_are_server_side_with_count_and_links_that_keep_the_query(self) -> None:
        response = self.list_tickets(self.scene.client_user, page_size=10, ordering="created_at", page=2)

        body = response.json()
        self.assertEqual(body["count"], 25)
        self.assertEqual([ticket["id"] for ticket in body["results"]], [t.id for t in self.tickets][10:20])
        for link in (body["next"], body["previous"]):
            self.assertIn("ordering=created_at", link)
            self.assertIn("page_size=10", link)
        self.assertIn("page=3", body["next"])

    def test_default_page_size_is_ten_and_the_maximum_is_fifty(self) -> None:
        self.assertEqual(len(self.listed_ids(self.scene.client_user)), 10)
        self.assertEqual(len(self.listed_ids(self.scene.client_user, page_size=50)), 25)

    def test_count_reflects_filters_and_search_before_slicing(self) -> None:
        add_issue(self.tickets[0], "Broken lift")
        add_issue(self.tickets[1], "Broken lift")

        body = self.list_tickets(self.scene.client_user, search="lift", page_size=1).json()

        self.assertEqual(body["count"], 2)
        self.assertEqual(len(body["results"]), 1)

    def test_a_page_past_the_end_is_a_validation_error_but_an_empty_listing_is_a_normal_200(self) -> None:
        self.assertEqual(self.list_tickets(self.scene.client_user, page=4).status_code, status.HTTP_400_BAD_REQUEST)

        empty = self.list_tickets(create_user(UserRole.CLIENT))
        self.assertEqual(empty.status_code, status.HTTP_200_OK)
        self.assertEqual(empty.json()["results"], [])


class ListRepresentationTests(ListingTestCase):
    def test_item_has_the_card_shape(self) -> None:
        scene = create_scene()
        floor = create_floor(scene.property_record)
        map_floor_to_office(floor, scene.office)
        scene.ticket.floors.add(floor)
        add_issue(scene.ticket, "AC not cooling")
        move_to_assessment_stage(scene.ticket, scene.worker)

        item = self.list_tickets(scene.client_user).json()["results"][0]

        self.assertEqual(item["id"], scene.ticket.id)
        self.assertEqual(item["ticket_number"], f"TKT-{scene.ticket.id}")
        self.assertEqual(item["client"], {"id": scene.client.id, "name": scene.client.name})
        self.assertEqual(item["client_office"], {"id": scene.office.id, "name": scene.office.name})
        self.assertEqual([issue["name"] for issue in item["issues"]], ["AC not cooling"])
        self.assertEqual(item["floors"], [{"id": floor.id, "name": floor.name}])
        self.assertEqual(item["workflow_stage"], WorkflowStage.PENDING_TECHNICIAN_ASSESSMENT)
        self.assertEqual(item["status"], "OPEN")
        self.assertEqual(
            item["created_by"],
            {
                "id": scene.client_user.id,
                "name": scene.client_user.name,
                "role": "CLIENT",
                "role_label": "Client POC",
            },
        )
        self.assertEqual(item["current_department"], {"id": scene.department.id, "name": scene.department.name})
        self.assertEqual(
            [(person["role"], person["role_label"]) for person in item["current_assignees"]],
            [("DEPARTMENT_POC", f"{scene.department.name} Manager"), ("WORKER", "Technician")],
        )
        self.assertNotIn("email", item["created_by"])

    def test_unassigned_ticket_lists_only_the_department_poc_as_assignee(self) -> None:
        scene = create_scene()

        item = self.list_tickets(scene.client_user).json()["results"][0]

        self.assertEqual([person["id"] for person in item["current_assignees"]], [scene.poc.id])

    def test_query_count_does_not_grow_with_the_number_of_tickets(self) -> None:
        scene = create_scene()
        self.populate_card(scene.ticket, scene)
        with CaptureQueriesContext(connection) as one_ticket:
            self.list_tickets(scene.client_user)

        for _ in range(5):
            card = create_ticket(
                client_office=scene.office,
                origin_department=create_department(),
                # A POC creator costs a query per row unless poc_department is loaded with the Ticket.
                created_by=create_department().poc_user,
            )
            self.populate_card(card, scene)
        with CaptureQueriesContext(connection) as six_tickets:
            response = self.list_tickets(scene.client_user)

        self.assertEqual(response.json()["count"], 6)
        self.assertEqual(len(six_tickets), len(one_ticket))

    @staticmethod
    def populate_card(ticket, scene) -> None:
        for number in range(2):
            add_issue(ticket, f"Issue {ticket.id}-{number}")
        floor = create_floor(scene.property_record)
        map_floor_to_office(floor, scene.office)
        ticket.floors.add(floor)
        worker = create_worker(ticket.current_department)
        move_to_assessment_stage(ticket, worker)


class ActionRequiredTests(ListingTestCase):
    def action_required(self, user, ticket) -> bool:
        self.client.force_authenticate(user)
        items = self.client.get(LIST_URL, {"tab": "open", "page_size": 50}).json()["results"]
        return next(item for item in items if item["id"] == ticket.id)["action_required"]

    def test_department_poc_is_waited_on_at_assignment_and_review_but_not_in_between(self) -> None:
        scene = create_scene()
        self.assertTrue(self.action_required(scene.poc, scene.ticket))

        move_to_assessment_stage(scene.ticket, scene.worker)
        self.assertFalse(self.action_required(scene.poc, scene.ticket))

        scene.ticket.workflow_stage = WorkflowStage.PENDING_DEPARTMENT_POC_REVIEW
        scene.ticket.status = "TECHNICIAN_CLOSED"
        scene.ticket.save()
        self.assertTrue(self.action_required(scene.poc, scene.ticket))

    def test_only_the_active_worker_is_waited_on_at_the_assessment_stage(self) -> None:
        scene = create_scene()
        move_to_assessment_stage(scene.ticket, scene.worker)
        other_worker = create_worker(scene.department)
        create_assignment(scene.ticket, other_worker, ended_at=timezone.now(), end_reason="REASSIGNED")

        self.assertTrue(self.action_required(scene.worker, scene.ticket))
        self.assertFalse(self.action_required(other_worker, scene.ticket))

    def test_clients_and_facility_managers_are_never_waited_on(self) -> None:
        scene = create_scene()

        self.assertFalse(self.action_required(scene.client_user, scene.ticket))
        self.assertFalse(self.action_required(scene.facility_manager, scene.ticket))

    def test_closed_tickets_never_require_action(self) -> None:
        scene = create_scene()
        close_ticket(scene.ticket, scene.client_user)

        self.client.force_authenticate(scene.poc)
        item = self.client.get(LIST_URL, {"tab": "closed"}).json()["results"][0]

        self.assertFalse(item["action_required"])


class FilterOptionsTests(ListingTestCase):
    URL = "/api/v1/tickets/filter-options/"

    def test_options_come_only_from_the_users_visible_tickets_and_are_sorted_by_name(self) -> None:
        scene = create_scene()
        create_scene()  # another Client, Department, and Facility Manager the user cannot see

        self.client.force_authenticate(scene.poc)
        body = self.client.get(self.URL).json()

        self.assertEqual(body["clients"], [{"id": scene.client.id, "name": scene.client.name}])
        self.assertEqual(body["departments"], [{"id": scene.department.id, "name": scene.department.name}])
        self.assertEqual(
            body["facility_managers"], [{"id": scene.facility_manager.id, "name": scene.facility_manager.name}]
        )
        self.assertEqual(
            [stage["value"] for stage in body["workflow_stages"]], [stage.value for stage in WorkflowStage]
        )

    def test_departments_are_the_current_department_and_closed_tickets_count(self) -> None:
        scene = create_scene()
        forwarded_to = create_department()
        scene.ticket.current_department = forwarded_to
        scene.ticket.save()
        close_ticket(scene.ticket, scene.client_user)

        self.client.force_authenticate(scene.facility_manager)
        body = self.client.get(self.URL).json()

        self.assertEqual([department["id"] for department in body["departments"]], [forwarded_to.id])

    def test_a_user_with_no_tickets_gets_empty_lists_but_all_stages(self) -> None:
        self.client.force_authenticate(create_user(UserRole.CLIENT))

        body = self.client.get(self.URL).json()

        self.assertEqual((body["clients"], body["departments"], body["facility_managers"]), ([], [], []))
        self.assertEqual(len(body["workflow_stages"]), 3)

    def test_workers_only_see_options_for_their_assigned_tickets(self) -> None:
        scene = create_scene()
        move_to_assessment_stage(scene.ticket, scene.worker)
        create_scene()

        self.client.force_authenticate(scene.worker)
        body = self.client.get(self.URL).json()

        self.assertEqual([client["id"] for client in body["clients"]], [scene.client.id])

    def test_requires_authentication(self) -> None:
        self.assertEqual(self.client.get(self.URL).status_code, status.HTTP_401_UNAUTHORIZED)

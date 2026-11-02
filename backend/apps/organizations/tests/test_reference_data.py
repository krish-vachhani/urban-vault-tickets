"""Successful responses, filtering and ranking for the reference-data endpoints."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.organizations.models import Issue
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
from apps.tickets.models import TicketIssue
from apps.tickets.tests.helpers import create_ticket


def names(response) -> list[str]:
    return [item["name"] for item in response.json()["results"]]


class MyClientsTests(APITestCase):
    def test_returns_only_the_callers_active_clients_sorted_by_name(self) -> None:
        user = create_user(UserRole.CLIENT)
        second = create_client()
        second.name = "Beta"
        second.save()
        first = create_client()
        first.name = "Alpha"
        first.save()
        inactive = create_client()
        inactive.is_active = False
        inactive.save()
        for client in (second, first, inactive):
            map_user_to_client(user, client)
        create_client()  # unmapped
        self.client.force_authenticate(user)

        response = self.client.get("/api/v1/me/clients/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"results": [{"id": first.id, "name": "Alpha"}, {"id": second.id, "name": "Beta"}]})

    def test_user_without_clients_gets_an_empty_result(self) -> None:
        self.client.force_authenticate(create_user(UserRole.CLIENT))

        response = self.client.get("/api/v1/me/clients/")

        self.assertEqual(response.json(), {"results": []})

    def test_user_id_query_parameter_is_ignored(self) -> None:
        caller = create_user(UserRole.CLIENT)
        other_user = create_user(UserRole.CLIENT)
        map_user_to_client(other_user, create_client())
        self.client.force_authenticate(caller)

        response = self.client.get(f"/api/v1/me/clients/?user_id={other_user.id}")

        self.assertEqual(response.json(), {"results": []})


class ClientOfficesTests(APITestCase):
    def test_returns_active_offices_with_property_and_floor_count(self) -> None:
        user = create_user(UserRole.CLIENT)
        client = create_client()
        map_user_to_client(user, client)
        property_record = create_property()
        office = create_office(client, property_record)
        office.code = "1317"
        office.save()
        for _ in range(2):
            map_floor_to_office(create_floor(property_record), office)
        inactive_office = create_office(client)
        inactive_office.is_active = False
        inactive_office.save()
        self.client.force_authenticate(user)

        response = self.client.get(f"/api/v1/clients/{client.id}/offices/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["results"],
            [
                {
                    "id": office.id,
                    "name": office.name,
                    "code": "1317",
                    "property": {"id": property_record.id, "name": property_record.name},
                    "floor_count": 2,
                }
            ],
        )

    def test_client_user_and_department_poc_get_offices_in_every_property(self) -> None:
        client = create_client()
        offices = [create_office(client), create_office(client)]
        for user in (create_user(UserRole.CLIENT), create_department().poc_user):
            with self.subTest(role=user.role):
                map_user_to_client(user, client)
                self.client.force_authenticate(user)

                response = self.client.get(f"/api/v1/clients/{client.id}/offices/")

                self.assertCountEqual([item["id"] for item in response.json()["results"]], [o.id for o in offices])

    def test_facility_manager_only_gets_offices_in_managed_properties(self) -> None:
        manager = create_user(UserRole.FACILITY_MANAGER)
        client = create_client()
        map_user_to_client(manager, client)
        managed_office = create_office(client, create_property(facility_manager=manager))
        create_office(client)  # same Client, Property managed by someone else
        self.client.force_authenticate(manager)

        response = self.client.get(f"/api/v1/clients/{client.id}/offices/")

        self.assertEqual([item["id"] for item in response.json()["results"]], [managed_office.id])

    def test_facility_manager_without_managed_offices_gets_an_empty_result(self) -> None:
        manager = create_user(UserRole.FACILITY_MANAGER)
        client = create_client()
        map_user_to_client(manager, client)
        create_office(client)
        self.client.force_authenticate(manager)

        response = self.client.get(f"/api/v1/clients/{client.id}/offices/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"results": []})


class OfficeFloorsTests(APITestCase):
    def test_returns_only_floors_mapped_to_the_office(self) -> None:
        user = create_user(UserRole.CLIENT)
        client = create_client()
        map_user_to_client(user, client)
        property_record = create_property()
        office = create_office(client, property_record)
        mapped_floor = create_floor(property_record)
        map_floor_to_office(mapped_floor, office)
        create_floor(property_record)  # in the Property but not mapped to this Office
        self.client.force_authenticate(user)

        response = self.client.get(f"/api/v1/client-offices/{office.id}/floors/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"results": [{"id": mapped_floor.id, "name": mapped_floor.name}]})

    def test_office_without_floors_returns_an_empty_result(self) -> None:
        user = create_user(UserRole.CLIENT)
        office = create_office()
        map_user_to_client(user, office.client)
        self.client.force_authenticate(user)

        response = self.client.get(f"/api/v1/client-offices/{office.id}/floors/")

        self.assertEqual(response.json(), {"results": []})


class DepartmentTests(APITestCase):
    def test_returns_active_departments_only(self) -> None:
        active = create_department()
        inactive = create_department()
        inactive.is_active = False
        inactive.save()
        self.client.force_authenticate(create_user(UserRole.CLIENT))

        response = self.client.get("/api/v1/departments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"results": [{"id": active.id, "name": active.name}]})


class IssueSearchTests(APITestCase):
    def setUp(self) -> None:
        self.technical = create_department()
        self.it = create_department()
        self.ac_issue = Issue.objects.create(name="AC not cooling", department=self.technical)
        self.leak_issue = Issue.objects.create(name="Water leakage", department=self.technical)
        self.vpn_issue = Issue.objects.create(name="VPN access (AC adapter)", department=self.it)
        Issue.objects.create(name="AC retired issue", department=self.technical, is_active=False)
        self.client.force_authenticate(create_user(UserRole.CLIENT))

    def search(self, query: str = ""):
        return self.client.get(f"/api/v1/issues/{query}")

    def test_returns_active_issues_with_their_department(self) -> None:
        response = self.search()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(names(response), ["AC not cooling", "VPN access (AC adapter)", "Water leakage"])
        first = response.json()["results"][0]
        self.assertEqual(first["department"], {"id": self.technical.id, "name": self.technical.name})

    def test_search_matches_issue_name_case_insensitively(self) -> None:
        self.assertEqual(names(self.search("?search=ac")), ["AC not cooling", "VPN access (AC adapter)"])

    def test_department_filter_narrows_the_search(self) -> None:
        response = self.search(f"?department_id={self.technical.id}&search=ac")

        self.assertEqual(names(response), ["AC not cooling"])

    def test_unknown_department_returns_an_empty_result(self) -> None:
        self.assertEqual(self.search("?department_id=999999").json(), {"results": []})

    def test_malformed_department_id_is_a_validation_error(self) -> None:
        response = self.search("?department_id=abc")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("department_id", response.json()["error"]["details"])

    def test_results_are_limited_to_twenty(self) -> None:
        for number in range(25):
            Issue.objects.create(name=f"Bulk issue {number}", department=self.it)

        self.assertEqual(len(self.search("?search=bulk").json()["results"]), 20)


class QuickIssueTests(APITestCase):
    def setUp(self) -> None:
        self.user = create_user(UserRole.CLIENT)
        self.reference_client = create_client()
        map_user_to_client(self.user, self.reference_client)
        self.office = create_office(self.reference_client)
        self.department = create_department()
        self.now = timezone.now()
        self.client.force_authenticate(self.user)

    def report(self, issues: list[Issue], days_ago: int, office=None, **ticket_fields) -> None:
        ticket = create_ticket(
            client_office=office or self.office,
            origin_department=self.department,
            created_at=self.now - timedelta(days=days_ago),
            **ticket_fields,
        )
        for issue in issues:
            TicketIssue.objects.create(ticket=ticket, issue=issue)

    def make_issue(self, name: str, **fields) -> Issue:
        return Issue.objects.create(name=name, department=self.department, **fields)

    def get_quick_issues(self) -> list[dict]:
        response = self.client.get(f"/api/v1/clients/{self.reference_client.id}/quick-issues/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()["results"]

    def test_ranks_by_frequency_then_most_recent_report(self) -> None:
        most_frequent = self.make_issue("Most frequent")
        tie_recent = self.make_issue("Tie recent")
        tie_old = self.make_issue("Tie old")
        rare = self.make_issue("Rare")
        self.report([most_frequent], days_ago=30)
        self.report([most_frequent, tie_old], days_ago=20)
        self.report([most_frequent, tie_recent], days_ago=10)
        self.report([tie_old, tie_recent], days_ago=15)
        self.report([rare], days_ago=1)

        results = self.get_quick_issues()

        # most_frequent 3x; tie_recent and tie_old 2x each (tie_recent reported more recently); rare 1x.
        self.assertEqual([item["name"] for item in results], ["Most frequent", "Tie recent", "Tie old", "Rare"])
        self.assertEqual([item["occurrences"] for item in results], [3, 2, 2, 1])

    def test_returns_at_most_four_issues(self) -> None:
        for number in range(6):
            self.report([self.make_issue(f"Issue {number}")], days_ago=number)

        self.assertEqual(len(self.get_quick_issues()), 4)

    def test_response_shape_and_last_reported_time(self) -> None:
        issue = self.make_issue("AC not cooling")
        self.report([issue], days_ago=5)

        (result,) = self.get_quick_issues()

        self.assertEqual(set(result), {"id", "name", "department_id", "occurrences", "last_reported_at"})
        self.assertEqual(result["department_id"], self.department.id)
        self.assertTrue(result["last_reported_at"].endswith("Z"))

    def test_counts_tickets_across_all_offices_and_closed_tickets(self) -> None:
        issue = self.make_issue("Shared issue")
        self.report([issue], days_ago=3)
        self.report([issue], days_ago=2, office=create_office(self.reference_client))
        self.report([issue], days_ago=1, status="CLOSED", closed_by=self.user, closed_at=self.now)

        (result,) = self.get_quick_issues()

        self.assertEqual(result["occurrences"], 3)

    def test_ignores_other_clients_tickets_and_inactive_issues(self) -> None:
        other_clients_issue = self.make_issue("Other client's issue")
        retired_issue = self.make_issue("Retired", is_active=False)
        self.report([other_clients_issue], days_ago=1, office=create_office())
        self.report([retired_issue], days_ago=1)

        self.assertEqual(self.get_quick_issues(), [])

    def test_issue_never_reported_is_not_a_quick_issue(self) -> None:
        create_issue(self.department)

        self.assertEqual(self.get_quick_issues(), [])

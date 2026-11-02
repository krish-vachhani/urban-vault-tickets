"""Authentication and scope boundaries: users must not enumerate unrelated reference data."""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.organizations.tests.helpers import (
    create_client,
    create_floor,
    create_office,
    create_property,
    create_user,
    map_floor_to_office,
    map_user_to_client,
)

ANY_ID = 1


class AuthenticationRequiredTests(APITestCase):
    def test_every_endpoint_rejects_a_request_without_a_token(self) -> None:
        urls = [
            "/api/v1/me/clients/",
            f"/api/v1/clients/{ANY_ID}/offices/",
            f"/api/v1/client-offices/{ANY_ID}/floors/",
            "/api/v1/departments/",
            "/api/v1/issues/",
            f"/api/v1/clients/{ANY_ID}/quick-issues/",
            f"/api/v1/tickets/{ANY_ID}/eligible-workers/",
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
                self.assertEqual(response.json()["error"]["code"], "NOT_AUTHENTICATED")


class ClientScopeTests(APITestCase):
    """Client-addressed endpoints return 404 for a Client the user is not mapped to."""

    def setUp(self) -> None:
        self.user = create_user(UserRole.CLIENT)
        self.own_client = create_client()
        map_user_to_client(self.user, self.own_client)
        self.unrelated_client = create_client()
        self.unrelated_office = create_office(self.unrelated_client)
        self.client.force_authenticate(self.user)

    def assert_not_found(self, url: str) -> None:
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_offices_of_an_unmapped_client_are_not_found(self) -> None:
        self.assert_not_found(f"/api/v1/clients/{self.unrelated_client.id}/offices/")

    def test_quick_issues_of_an_unmapped_client_are_not_found(self) -> None:
        self.assert_not_found(f"/api/v1/clients/{self.unrelated_client.id}/quick-issues/")

    def test_floors_of_an_unmapped_clients_office_are_not_found(self) -> None:
        self.assert_not_found(f"/api/v1/client-offices/{self.unrelated_office.id}/floors/")

    def test_unknown_and_unmapped_ids_get_the_same_response(self) -> None:
        unmapped = self.client.get(f"/api/v1/clients/{self.unrelated_client.id}/offices/")
        unknown = self.client.get("/api/v1/clients/999999/offices/")

        self.assertEqual(unmapped.status_code, unknown.status_code)
        self.assertEqual(unmapped.json(), unknown.json())

    def test_inactive_client_is_not_found_even_when_mapped(self) -> None:
        self.own_client.is_active = False
        self.own_client.save()

        self.assert_not_found(f"/api/v1/clients/{self.own_client.id}/offices/")

    def test_inactive_office_floors_are_not_found(self) -> None:
        office = create_office(self.own_client)
        office.is_active = False
        office.save()

        self.assert_not_found(f"/api/v1/client-offices/{office.id}/floors/")

    def test_malformed_ids_are_validation_errors(self) -> None:
        for url in (
            "/api/v1/clients/abc/offices/",
            "/api/v1/clients/abc/quick-issues/",
            "/api/v1/client-offices/abc/floors/",
            "/api/v1/tickets/abc/eligible-workers/",
        ):
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")


class FacilityManagerOfficeScopeTests(APITestCase):
    def setUp(self) -> None:
        self.manager = create_user(UserRole.FACILITY_MANAGER)
        self.reference_client = create_client()
        map_user_to_client(self.manager, self.reference_client)
        self.managed_property = create_property(facility_manager=self.manager)
        self.other_property = create_property()
        self.managed_office = create_office(self.reference_client, self.managed_property)
        self.other_office = create_office(self.reference_client, self.other_property)
        self.managed_floor = create_floor(self.managed_property)
        map_floor_to_office(self.managed_floor, self.managed_office)
        map_floor_to_office(create_floor(self.other_property), self.other_office)
        self.client.force_authenticate(self.manager)

    def test_floors_of_a_managed_office_are_returned(self) -> None:
        response = self.client.get(f"/api/v1/client-offices/{self.managed_office.id}/floors/")

        self.assertEqual([floor["id"] for floor in response.json()["results"]], [self.managed_floor.id])

    def test_floors_of_an_office_in_another_managers_property_are_not_found(self) -> None:
        # The Client is mapped to this manager, but the Property is not managed by them.
        response = self.client.get(f"/api/v1/client-offices/{self.other_office.id}/floors/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_client_user_is_not_limited_by_property_manager(self) -> None:
        client_user = create_user(UserRole.CLIENT)
        map_user_to_client(client_user, self.reference_client)
        self.client.force_authenticate(client_user)

        response = self.client.get(f"/api/v1/client-offices/{self.other_office.id}/floors/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import UserRole
from apps.accounts.tests.helpers import ME_URL
from apps.organizations.models import UserClient
from apps.organizations.tests.helpers import (
    create_client,
    create_department,
    create_user,
    create_worker,
)


class CurrentUserTests(APITestCase):
    def get_me(self, user):
        return self.client.get(ME_URL, HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def test_client_user_gets_mapped_active_clients_and_no_department(self) -> None:
        user = create_user(UserRole.CLIENT)
        harness = create_client()
        acme = create_client()
        inactive_client = create_client()
        inactive_client.is_active = False
        inactive_client.save()
        unrelated_client = create_client()
        for mapped_client in (harness, acme, inactive_client):
            UserClient.objects.create(user=user, client=mapped_client)

        body = self.get_me(user).json()

        self.assertEqual(body["role"], UserRole.CLIENT)
        self.assertEqual(body["role_label"], "Client POC")
        self.assertIsNone(body["department"])
        returned_ids = {client["id"] for client in body["clients"]}
        self.assertEqual(returned_ids, {harness.id, acme.id})
        self.assertNotIn(unrelated_client.id, returned_ids)

    def test_facility_manager_has_no_department(self) -> None:
        body = self.get_me(create_user(UserRole.FACILITY_MANAGER)).json()

        self.assertEqual(body["role_label"], "Facility Manager")
        self.assertIsNone(body["department"])
        self.assertEqual(body["clients"], [])

    def test_department_poc_gets_the_department_they_lead(self) -> None:
        department = create_department()

        body = self.get_me(department.poc_user).json()

        self.assertEqual(body["department"], {"id": department.id, "name": department.name})
        self.assertEqual(body["role_label"], f"{department.name} Manager")

    def test_worker_gets_the_department_they_belong_to(self) -> None:
        department = create_department()

        body = self.get_me(create_worker(department)).json()

        self.assertEqual(body["department"], {"id": department.id, "name": department.name})
        self.assertEqual(body["role_label"], "Technician")

    def test_response_never_contains_token_or_password_fields(self) -> None:
        body = self.get_me(create_user(UserRole.CLIENT)).json()

        self.assertEqual(set(body), {"id", "name", "email", "role", "role_label", "department", "clients"})

    def test_role_comes_from_the_database_not_the_token(self) -> None:
        user = create_user(UserRole.CLIENT)
        token = str(AccessToken.for_user(user))
        user.role = UserRole.FACILITY_MANAGER
        user.save()

        response = self.client.get(ME_URL, HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(response.json()["role"], UserRole.FACILITY_MANAGER)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

"""Database rules for the organizations schema (readmes/README-database-schema.md §2.2–§2.10, §3)."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from apps.accounts.models import UserRole
from apps.organizations.models import (
    ClientOffice,
    ClientOfficeFloor,
    Department,
    DepartmentWorker,
    Floor,
    Issue,
    Property,
    UserClient,
)
from apps.organizations.role_labels import get_role_label
from apps.organizations.tests.helpers import (
    create_client,
    create_department,
    create_floor,
    create_issue,
    create_office,
    create_property,
    create_user,
    create_worker,
)


class UniquenessConstraintTests(TestCase):
    def test_user_is_mapped_to_a_client_only_once(self) -> None:
        user, client = create_user(UserRole.CLIENT), create_client()
        UserClient.objects.create(user=user, client=client)

        with self.assertRaises(IntegrityError), transaction.atomic():
            UserClient.objects.create(user=user, client=client)

    def test_user_can_be_mapped_to_several_clients(self) -> None:
        user = create_user(UserRole.CLIENT)
        UserClient.objects.create(user=user, client=create_client())
        UserClient.objects.create(user=user, client=create_client())

        self.assertEqual(user.clients.count(), 2)

    def test_floor_name_is_unique_within_a_property_only(self) -> None:
        property_record = create_property()
        Floor.objects.create(property=property_record, name="2F")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Floor.objects.create(property=property_record, name="2F")
        Floor.objects.create(property=create_property(), name="2F")

    def test_office_occupies_a_floor_only_once(self) -> None:
        property_record = create_property()
        office, floor = create_office(property_record=property_record), create_floor(property_record)
        ClientOfficeFloor.objects.create(client_office=office, floor=floor)

        with self.assertRaises(IntegrityError), transaction.atomic():
            ClientOfficeFloor.objects.create(client_office=office, floor=floor)

    def test_floor_can_be_shared_by_two_offices(self) -> None:
        property_record = create_property()
        floor = create_floor(property_record)
        for _ in range(2):
            office = create_office(property_record=property_record)
            ClientOfficeFloor.objects.create(client_office=office, floor=floor)

        self.assertEqual(floor.client_offices.count(), 2)

    def test_office_code_is_unique_within_a_client(self) -> None:
        client = create_client()
        ClientOffice.objects.create(client=client, property=create_property(), name="One", code="1317")

        with self.assertRaises(IntegrityError), transaction.atomic():
            ClientOffice.objects.create(client=client, property=create_property(), name="Two", code="1317")

    def test_same_office_code_is_allowed_for_different_clients(self) -> None:
        ClientOffice.objects.create(client=create_client(), property=create_property(), name="One", code="1317")
        ClientOffice.objects.create(client=create_client(), property=create_property(), name="Two", code="1317")

    def test_blank_office_codes_do_not_collide(self) -> None:
        client = create_client()
        ClientOffice.objects.create(client=client, property=create_property(), name="One")
        ClientOffice.objects.create(client=client, property=create_property(), name="Two")

    def test_department_name_is_unique(self) -> None:
        department = create_department()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Department.objects.create(name=department.name, poc_user=create_user(UserRole.DEPARTMENT_POC))

    def test_poc_leads_only_one_department(self) -> None:
        department = create_department()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Department.objects.create(name="Another", poc_user=department.poc_user)

    def test_worker_belongs_to_only_one_department(self) -> None:
        worker = create_worker(create_department())

        with self.assertRaises(IntegrityError), transaction.atomic():
            DepartmentWorker.objects.create(department=create_department(), worker=worker)

    def test_department_can_have_several_workers(self) -> None:
        department = create_department()
        create_worker(department)
        create_worker(department)

        self.assertEqual(department.worker_memberships.count(), 2)

    def test_issue_name_is_unique_within_a_department_only(self) -> None:
        department = create_department()
        Issue.objects.create(department=department, name="AC not cooling")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Issue.objects.create(department=department, name="AC not cooling")
        Issue.objects.create(department=create_department(), name="AC not cooling")


class DeletionProtectionTests(TestCase):
    def test_department_with_issues_cannot_be_deleted(self) -> None:
        issue = create_issue()

        with self.assertRaises(ProtectedError):
            issue.department.delete()

    def test_facility_manager_of_a_property_cannot_be_deleted(self) -> None:
        property_record = create_property()

        with self.assertRaises(ProtectedError):
            property_record.facility_manager.delete()

    def test_client_with_offices_cannot_be_deleted(self) -> None:
        office = create_office()

        with self.assertRaises(ProtectedError):
            office.client.delete()


class RoleValidationTests(TestCase):
    """limit_choices_to restricts what admin forms accept (via full_clean). It is not service-level validation."""

    def test_property_manager_must_be_a_facility_manager(self) -> None:
        property_record = Property(name="Hub", facility_manager=create_user(UserRole.CLIENT))

        with self.assertRaises(ValidationError) as context:
            property_record.full_clean()
        self.assertIn("facility_manager", context.exception.message_dict)

    def test_department_poc_must_have_the_poc_role(self) -> None:
        department = Department(name="Technical", poc_user=create_user(UserRole.WORKER))

        with self.assertRaises(ValidationError) as context:
            department.full_clean()
        self.assertIn("poc_user", context.exception.message_dict)

    def test_department_worker_must_have_the_worker_role(self) -> None:
        membership = DepartmentWorker(department=create_department(), worker=create_user(UserRole.CLIENT))

        with self.assertRaises(ValidationError) as context:
            membership.full_clean()
        self.assertIn("worker", context.exception.message_dict)

    def test_department_poc_cannot_also_be_a_worker(self) -> None:
        poc = create_department().poc_user
        membership = DepartmentWorker(department=create_department(), worker=poc)

        with self.assertRaises(ValidationError):
            membership.full_clean()

    def test_valid_roles_pass_validation(self) -> None:
        Property(name="Hub", facility_manager=create_user(UserRole.FACILITY_MANAGER)).full_clean()
        Department(name="Technical", poc_user=create_user(UserRole.DEPARTMENT_POC)).full_clean()


class OfficeFloorValidationTests(TestCase):
    def test_floor_must_belong_to_the_offices_property(self) -> None:
        office = create_office()
        floor_in_other_property = create_floor()

        with self.assertRaises(ValidationError):
            ClientOfficeFloor(client_office=office, floor=floor_in_other_property).full_clean()

    def test_floor_in_the_same_property_is_valid(self) -> None:
        office = create_office()
        ClientOfficeFloor(client_office=office, floor=create_floor(office.property)).full_clean()


class RoleLabelTests(TestCase):
    def test_labels_match_the_api_conventions(self) -> None:
        department = create_department()
        department.name = "Technical"
        department.save()

        self.assertEqual(get_role_label(create_user(UserRole.CLIENT)), "Client POC")
        self.assertEqual(get_role_label(create_user(UserRole.FACILITY_MANAGER)), "Facility Manager")
        self.assertEqual(get_role_label(department.poc_user), "Technical Manager")
        self.assertEqual(get_role_label(create_worker(department)), "Technician")

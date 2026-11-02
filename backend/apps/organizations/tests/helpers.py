"""Small builders for test records. Tests never depend on the demo seed command."""

import itertools

from apps.accounts.models import User, UserRole
from apps.organizations.models import (
    Client,
    ClientOffice,
    ClientOfficeFloor,
    Department,
    DepartmentWorker,
    Floor,
    Issue,
    Property,
    UserClient,
)

_sequence = itertools.count(1)


def create_user(role: str) -> User:
    number = next(_sequence)
    # No password: these users never log in, and hashing one would slow every test.
    return User.objects.create_user(email=f"user{number}@example.test", name=f"User {number}", role=role)


def create_client() -> Client:
    return Client.objects.create(name=f"Client {next(_sequence)}")


def map_user_to_client(user: User, client: Client) -> UserClient:
    return UserClient.objects.create(user=user, client=client)


def create_property(facility_manager: User | None = None) -> Property:
    return Property.objects.create(
        name=f"Property {next(_sequence)}",
        facility_manager=facility_manager or create_user(UserRole.FACILITY_MANAGER),
    )


def create_floor(property_record: Property | None = None) -> Floor:
    return Floor.objects.create(property=property_record or create_property(), name=f"Floor {next(_sequence)}")


def create_office(client: Client | None = None, property_record: Property | None = None) -> ClientOffice:
    return ClientOffice.objects.create(
        client=client or create_client(),
        property=property_record or create_property(),
        name=f"Office {next(_sequence)}",
    )


def create_department() -> Department:
    return Department.objects.create(
        name=f"Department {next(_sequence)}", poc_user=create_user(UserRole.DEPARTMENT_POC)
    )


def create_worker(department: Department) -> User:
    worker = create_user(UserRole.WORKER)
    DepartmentWorker.objects.create(department=department, worker=worker)
    return worker


def create_issue(department: Department | None = None) -> Issue:
    return Issue.objects.create(name=f"Issue {next(_sequence)}", department=department or create_department())


def map_floor_to_office(floor: Floor, office: ClientOffice) -> ClientOfficeFloor:
    return ClientOfficeFloor.objects.create(client_office=office, floor=floor)

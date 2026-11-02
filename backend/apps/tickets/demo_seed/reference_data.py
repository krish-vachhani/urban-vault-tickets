"""Demo users, organizations, locations, Departments, and Issues.

Content follows readmes/README-seed-data.md §2–§4. Every function uses
get_or_create / update_or_create on natural keys, so running the seed again
never creates duplicates.
"""

from dataclasses import dataclass

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


@dataclass(frozen=True)
class DemoUser:
    email: str
    name: str
    role: str
    client_names: tuple[str, ...]


@dataclass(frozen=True)
class DemoProperty:
    name: str
    address: str
    facility_manager_email: str
    floor_names: tuple[str, ...]


@dataclass(frozen=True)
class DemoOffice:
    name: str
    client_name: str
    property_name: str
    floor_names: tuple[str, ...]


@dataclass(frozen=True)
class DemoDepartment:
    name: str
    poc_email: str
    worker_emails: tuple[str, ...]
    issue_names: tuple[str, ...]


CLIENT_NAMES = ("Harness", "Acme")

CHAITANYA = "chaitanya.m@urbanvault.test"
PRIYA = "priya.r@urbanvault.test"
NEHA = "neha.k@urbanvault.test"
CHANDAN = "chandan.s@urbanvault.test"
MEERA = "meera.j@urbanvault.test"
DHANANJAYA = "dhananjaya.m@urbanvault.test"
ABDUL = "abdul@urbanvault.test"
LAKSHMI = "lakshmi.n@urbanvault.test"
SURESH = "suresh.b@urbanvault.test"
PRAKASH = "prakash.k@urbanvault.test"
RAVI = "ravi.t@urbanvault.test"
IMRAN = "imran.s@urbanvault.test"
KAVYA = "kavya.p@urbanvault.test"
MANOJ = "manoj.e@urbanvault.test"

DEMO_USERS = (
    DemoUser(CHAITANYA, "Chaitanya M", UserRole.CLIENT, ("Harness",)),
    DemoUser(PRIYA, "Priya R", UserRole.CLIENT, CLIENT_NAMES),
    DemoUser(NEHA, "Neha K", UserRole.CLIENT, ("Acme",)),
    DemoUser(CHANDAN, "Chandan S", UserRole.FACILITY_MANAGER, CLIENT_NAMES),
    DemoUser(MEERA, "Meera J", UserRole.FACILITY_MANAGER, CLIENT_NAMES),
    DemoUser(DHANANJAYA, "Dhananjaya Murthy", UserRole.DEPARTMENT_POC, CLIENT_NAMES),
    DemoUser(ABDUL, "Abdul", UserRole.DEPARTMENT_POC, ("Harness",)),
    DemoUser(LAKSHMI, "Lakshmi N", UserRole.DEPARTMENT_POC, ("Harness",)),
    DemoUser(SURESH, "Suresh B", UserRole.DEPARTMENT_POC, ("Acme",)),
    DemoUser(PRAKASH, "Prakash Kumar", UserRole.WORKER, ()),
    DemoUser(RAVI, "Ravi T", UserRole.WORKER, ()),
    DemoUser(IMRAN, "Imran S", UserRole.WORKER, ()),
    DemoUser(KAVYA, "Kavya P", UserRole.WORKER, ()),
    DemoUser(MANOJ, "Manoj E", UserRole.WORKER, ()),
)

DEMO_PROPERTIES = (
    DemoProperty("Koramangala Hub", "80 Feet Road, Koramangala, Bengaluru", CHANDAN, ("1F", "2F", "3F", "4F")),
    DemoProperty("HSR Layout Hub", "27th Main, HSR Layout, Bengaluru", MEERA, ("GF", "1F", "2F")),
)

# Each Office shows a different Floor rule: several Floors, none, or exactly one.
DEMO_OFFICES = (
    DemoOffice("Harness-1317", "Harness", "Koramangala Hub", ("2F", "3F")),
    DemoOffice("HSR-1317", "Harness", "HSR Layout Hub", ()),
    DemoOffice("Acme-0410", "Acme", "Koramangala Hub", ("4F",)),
    DemoOffice("Acme-2201", "Acme", "HSR Layout Hub", ("1F", "2F")),
)

DEMO_DEPARTMENTS = (
    DemoDepartment(
        "Technical",
        DHANANJAYA,
        (PRAKASH, RAVI),
        ("AC not cooling", "Lift not working", "Water leakage"),
    ),
    DemoDepartment(
        "IT",
        ABDUL,
        (IMRAN,),
        ("Internet not working", "Wi-Fi slow", "Printer not working"),
    ),
    DemoDepartment(
        "Housekeeping",
        LAKSHMI,
        (KAVYA,),
        ("Pantry not cleaned", "Washroom not cleaned"),
    ),
    DemoDepartment(
        "Electrical",
        SURESH,
        (MANOJ,),
        ("Lights flickering", "Power outage"),
    ),
)


def seed_reference_data(demo_password: str) -> None:
    """Create or refresh every non-Ticket record."""
    users_by_email = _seed_users(demo_password)
    clients_by_name = {name: Client.objects.get_or_create(name=name)[0] for name in CLIENT_NAMES}
    _map_users_to_clients(users_by_email, clients_by_name)
    properties_by_name = _seed_properties_and_floors(users_by_email)
    _seed_offices(clients_by_name, properties_by_name)
    _seed_departments_workers_and_issues(users_by_email)


def _seed_users(demo_password: str) -> dict[str, User]:
    users_by_email = {}
    for demo_user in DEMO_USERS:
        user, _ = User.objects.update_or_create(
            email=demo_user.email,
            defaults={"name": demo_user.name, "role": demo_user.role, "is_active": True},
        )
        # update_or_create stores values as given, so the password must be hashed explicitly.
        user.set_password(demo_password)
        user.save(update_fields=["password"])
        users_by_email[demo_user.email] = user
    return users_by_email


def _map_users_to_clients(users_by_email: dict[str, User], clients_by_name: dict[str, Client]) -> None:
    for demo_user in DEMO_USERS:
        for client_name in demo_user.client_names:
            UserClient.objects.get_or_create(user=users_by_email[demo_user.email], client=clients_by_name[client_name])


def _seed_properties_and_floors(users_by_email: dict[str, User]) -> dict[str, Property]:
    properties_by_name = {}
    for demo_property in DEMO_PROPERTIES:
        property_record, _ = Property.objects.update_or_create(
            name=demo_property.name,
            defaults={
                "address": demo_property.address,
                "facility_manager": users_by_email[demo_property.facility_manager_email],
            },
        )
        for floor_name in demo_property.floor_names:
            Floor.objects.get_or_create(property=property_record, name=floor_name)
        properties_by_name[demo_property.name] = property_record
    return properties_by_name


def _seed_offices(clients_by_name: dict[str, Client], properties_by_name: dict[str, Property]) -> None:
    for demo_office in DEMO_OFFICES:
        property_record = properties_by_name[demo_office.property_name]
        office, _ = ClientOffice.objects.update_or_create(
            client=clients_by_name[demo_office.client_name],
            name=demo_office.name,
            defaults={"property": property_record},
        )
        for floor_name in demo_office.floor_names:
            floor = Floor.objects.get(property=property_record, name=floor_name)
            ClientOfficeFloor.objects.get_or_create(client_office=office, floor=floor)


def _seed_departments_workers_and_issues(users_by_email: dict[str, User]) -> None:
    for demo_department in DEMO_DEPARTMENTS:
        department, _ = Department.objects.update_or_create(
            name=demo_department.name,
            defaults={"poc_user": users_by_email[demo_department.poc_email]},
        )
        for worker_email in demo_department.worker_emails:
            DepartmentWorker.objects.update_or_create(
                worker=users_by_email[worker_email], defaults={"department": department}
            )
        for issue_name in demo_department.issue_names:
            Issue.objects.get_or_create(department=department, name=issue_name)

"""Read-only queries for reference data, including role-based Client and Office scope."""

from django.db.models import Count, Exists, Max, OuterRef, Q, QuerySet

from apps.accounts.models import User, UserRole
from apps.organizations.models import Client, ClientOffice, Department, Floor, Issue, UserClient

ISSUE_SEARCH_RESULT_LIMIT = 20
QUICK_ISSUE_LIMIT = 4


def get_user_clients(user: User) -> QuerySet[Client]:
    """Active Clients the user is mapped to through UserClient."""
    return Client.objects.filter(is_active=True, user_mappings__user=user).order_by("name", "id")


def get_authorized_offices(user: User) -> QuerySet[ClientOffice]:
    """Active Offices of the user's mapped Clients, narrowed by role.

    Facility Managers only get Offices in Properties they manage; a Client mapping
    alone is not enough (readmes/README-authorization.md §4, Create Ticket).
    """
    mapped_to_office_client = UserClient.objects.filter(user=user, client_id=OuterRef("client_id"))
    offices = ClientOffice.objects.filter(Exists(mapped_to_office_client), is_active=True, client__is_active=True)
    if user.role == UserRole.FACILITY_MANAGER:
        offices = offices.filter(property__facility_manager=user)
    return offices


def get_client_offices(user: User, client_id: int) -> QuerySet[ClientOffice]:
    return (
        get_authorized_offices(user)
        .filter(client_id=client_id)
        .select_related("property")
        .annotate(floor_count=Count("floor_mappings"))
        .order_by("name", "id")
    )


def get_office_floors(office: ClientOffice) -> QuerySet[Floor]:
    # The Property filter is a guard: a Floor of another Property is never offered.
    return Floor.objects.filter(
        office_mappings__client_office=office, property_id=office.property_id
    ).order_by("name", "id")


def get_active_departments() -> QuerySet[Department]:
    return Department.objects.filter(is_active=True).order_by("name", "id")


def search_issues(search_text: str, department_id: int | None) -> QuerySet[Issue]:
    issues = Issue.objects.filter(is_active=True).select_related("department")
    if search_text:
        issues = issues.filter(name__icontains=search_text)
    if department_id is not None:
        issues = issues.filter(department_id=department_id)
    return issues.order_by("name", "id")[:ISSUE_SEARCH_RESULT_LIMIT]


def get_quick_issues(client_id: int) -> QuerySet[Issue]:
    """The Client's most frequently reported active Issues, newest report breaking ties.

    Frequency counts distinct Tickets (TicketIssue is unique per Ticket and Issue) across
    all of the Client's Offices, open or closed (readmes/README-reference-data-apis.md §3.6).
    """
    for_this_client = Q(ticket_issues__ticket__client_office__client_id=client_id)
    return (
        Issue.objects.filter(is_active=True)
        .annotate(
            occurrences=Count("ticket_issues", filter=for_this_client),
            last_reported_at=Max("ticket_issues__ticket__created_at", filter=for_this_client),
        )
        .filter(occurrences__gt=0)
        .order_by("-occurrences", "-last_reported_at", "name", "id")[:QUICK_ISSUE_LIMIT]
    )

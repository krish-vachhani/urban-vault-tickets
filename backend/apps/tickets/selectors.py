"""Read-only Ticket queries: role-based visibility, listing, detail, filter options, feed, history."""

from django.db.models import CharField, Exists, F, JSONField, OuterRef, Prefetch, Q, QuerySet, Value

from apps.accounts.models import User, UserRole
from apps.organizations.models import Client, Department, Floor, Issue, UserClient
from apps.organizations.role_labels import get_name_with_role_label
from apps.tickets.models import (
    ActivityEventType,
    Ticket,
    TicketActivity,
    TicketAssignment,
    TicketComment,
    TicketIssue,
    TicketStatus,
)

TAB_OPEN = "open"
TAB_CLOSED = "closed"
# A Technician Closed Ticket stays in Open Tickets until the Client confirms the resolution.
OPEN_TAB_STATUSES = [TicketStatus.OPEN, TicketStatus.TECHNICIAN_CLOSED]

ORDER_NEWEST_FIRST = "-created_at"
ORDER_OLDEST_FIRST = "created_at"
# The ID breaks ties so page boundaries stay stable when Tickets share a timestamp.
TICKET_ORDERINGS = {
    ORDER_NEWEST_FIRST: ("-created_at", "-id"),
    ORDER_OLDEST_FIRST: ("created_at", "id"),
}

FEED_TYPE_ALL = "ALL"
FEED_TYPE_ACTIONS = "ACTIONS"
FEED_TYPE_COMMENTS = "COMMENTS"
FEED_ITEM_ACTION = "ACTION"
FEED_ITEM_COMMENT = "COMMENT"

# Name of the attribute that holds a Ticket's active assignments after the display prefetch.
ACTIVE_ASSIGNMENTS_ATTRIBUTE = "active_assignments"
FIRST_ASSIGNMENT_PREVIOUS_ASSIGNEE = "Unassigned"


def get_visible_tickets(user: User) -> QuerySet[Ticket]:
    """Tickets the user may see: their role's rule OR Tickets they created.

    Rules: readmes/README-authorization.md §1. Each rule is a foreign-key condition or
    an Exists subquery, so no join can duplicate a Ticket row.
    """
    return Ticket.objects.filter(_get_role_visibility(user) | Q(created_by=user))


def _get_role_visibility(user: User) -> Q:
    if user.role == UserRole.CLIENT:
        mapped_to_ticket_client = UserClient.objects.filter(
            user=user, client_id=OuterRef("client_office__client_id")
        )
        return Q(Exists(mapped_to_ticket_client))
    if user.role == UserRole.FACILITY_MANAGER:
        return Q(client_office__property__facility_manager=user)
    if user.role == UserRole.DEPARTMENT_POC:
        return Q(current_department__poc_user=user)
    # Workers keep read-only visibility after they stop being the assignee.
    ever_assigned_to_user = TicketAssignment.objects.filter(ticket=OuterRef("pk"), worker=user)
    return Q(Exists(ever_assigned_to_user))


def get_eligible_workers(ticket: Ticket) -> QuerySet[User]:
    """Active Workers in the Ticket's current Department; no Property or workload filter."""
    return User.objects.filter(
        is_active=True,
        role=UserRole.WORKER,
        department_membership__department_id=ticket.current_department_id,
    ).order_by("name", "id")


def get_active_assignment(ticket: Ticket) -> TicketAssignment | None:
    return TicketAssignment.objects.filter(ticket=ticket, ended_at__isnull=True).first()


def get_prefetched_active_assignment(ticket: Ticket) -> TicketAssignment | None:
    """The active assignment of a Ticket loaded through get_ticket_list or get_ticket_detail_queryset."""
    active_assignments = getattr(ticket, ACTIVE_ASSIGNMENTS_ATTRIBUTE)
    return active_assignments[0] if active_assignments else None


def _with_display_relations(tickets: QuerySet[Ticket]) -> QuerySet[Ticket]:
    """Load everything a Ticket card needs in a fixed number of queries.

    created_by needs poc_department because a POC's role label is "{Department} Manager".
    The current POC's label reuses the current_department row that select_related already loaded.
    """
    return tickets.select_related(
        "client_office__client",
        "created_by__poc_department",
        "current_department__poc_user",
    ).prefetch_related(
        Prefetch("issues", queryset=Issue.objects.order_by("name", "id")),
        Prefetch("floors", queryset=Floor.objects.order_by("name", "id")),
        Prefetch(
            "assignments",
            queryset=TicketAssignment.objects.filter(ended_at__isnull=True).select_related("worker"),
            to_attr=ACTIVE_ASSIGNMENTS_ATTRIBUTE,
        ),
    )


def get_ticket_list(
    user: User,
    *,
    tab: str = TAB_OPEN,
    search: str = "",
    client_id: int | None = None,
    department_id: int | None = None,
    facility_manager_id: int | None = None,
    workflow_stage: str | None = None,
    ordering: str = ORDER_NEWEST_FIRST,
) -> QuerySet[Ticket]:
    """The user's visible Tickets for one tab, narrowed by the filters and search, in display order.

    Visibility is applied first, so a filter can only narrow what the user may already see
    (readmes/README-ticket-listing-api.md §4 and §5).
    """
    tickets = get_visible_tickets(user)

    if tab == TAB_CLOSED:
        tickets = tickets.filter(status=TicketStatus.CLOSED)
    else:
        tickets = tickets.filter(status__in=OPEN_TAB_STATUSES)

    if client_id is not None:
        tickets = tickets.filter(client_office__client_id=client_id)
    if department_id is not None:
        # The Department currently responsible, not the one the Ticket started in.
        tickets = tickets.filter(current_department_id=department_id)
    if facility_manager_id is not None:
        tickets = tickets.filter(client_office__property__facility_manager_id=facility_manager_id)
    if workflow_stage is not None:
        tickets = tickets.filter(workflow_stage=workflow_stage)
    if search:
        # Exists never duplicates a Ticket whose several Issues all match.
        matching_issue = TicketIssue.objects.filter(ticket=OuterRef("pk"), issue__name__icontains=search)
        tickets = tickets.filter(Exists(matching_issue))

    return _with_display_relations(tickets).order_by(*TICKET_ORDERINGS[ordering])


def get_ticket_detail_queryset(user: User) -> QuerySet[Ticket]:
    """Visible Tickets with the extra relations the detail response shows."""
    return _with_display_relations(get_visible_tickets(user)).select_related(
        "origin_department", "closed_by__poc_department", "assessment__submitted_by"
    )


def get_filter_options(user: User) -> dict[str, QuerySet]:
    """Clients, Departments, and Facility Managers found among the user's visible Tickets.

    Departments are the Tickets' current Departments, matching the department_id filter.
    """
    visible_tickets = get_visible_tickets(user)
    return {
        "clients": Client.objects.filter(
            Exists(visible_tickets.filter(client_office__client_id=OuterRef("pk")))
        ).order_by("name", "id"),
        "departments": Department.objects.filter(
            Exists(visible_tickets.filter(current_department_id=OuterRef("pk")))
        ).order_by("name", "id"),
        "facility_managers": User.objects.filter(
            Exists(visible_tickets.filter(client_office__property__facility_manager_id=OuterRef("pk")))
        ).order_by("name", "id"),
    }


def get_activity_feed(ticket: Ticket, feed_type: str) -> QuerySet:
    """Actions and comments as one chronological feed of identically shaped rows.

    ALL is a single SQL UNION ALL, ordered and sliced by the database. Both querysets
    select the same aliases in the same order because a UNION matches columns by position.
    """
    actions = TicketActivity.objects.filter(ticket=ticket).values(
        item_id=F("id"),
        item_type=Value(FEED_ITEM_ACTION, output_field=CharField()),
        item_event_type=F("event_type"),
        item_actor_id=F("actor_id"),
        item_text=F("description"),
        item_metadata=F("metadata"),
        occurred_at=F("created_at"),
    )
    comments = TicketComment.objects.filter(ticket=ticket).values(
        item_id=F("id"),
        item_type=Value(FEED_ITEM_COMMENT, output_field=CharField()),
        item_event_type=Value(None, output_field=CharField()),
        item_actor_id=F("author_id"),
        item_text=F("body"),
        item_metadata=Value(None, output_field=JSONField()),
        occurred_at=F("created_at"),
    )

    if feed_type == FEED_TYPE_ACTIONS:
        feed = actions
    elif feed_type == FEED_TYPE_COMMENTS:
        feed = comments
    else:
        feed = actions.union(comments, all=True)
    return feed.order_by("occurred_at", "item_type", "item_id")


def get_feed_actors(actor_ids: set[int]) -> dict[int, User]:
    """The users behind one page of the feed, loaded in a single query."""
    users = User.objects.filter(id__in=actor_ids).select_related("poc_department")
    return {user.id: user for user in users}


def get_ticket_history(ticket: Ticket) -> dict[str, list]:
    """Assignment rows plus Department forwarding events, oldest first (not inferred from the current Worker)."""
    assignments = list(
        TicketAssignment.objects.filter(ticket=ticket)
        .select_related("worker", "assigned_by__poc_department")
        .order_by("assigned_at", "id")
    )
    # Each entry records who it replaced, so History can show "Unassigned → Worker".
    previous_assignee = FIRST_ASSIGNMENT_PREVIOUS_ASSIGNEE
    for assignment in assignments:
        assignment.previous_assignee = previous_assignee
        previous_assignee = get_name_with_role_label(assignment.worker)

    department_changes = list(
        TicketActivity.objects.filter(ticket=ticket, event_type=ActivityEventType.DEPARTMENT_CHANGED)
        .select_related("actor__poc_department")
        .order_by("created_at", "id")
    )
    return {"assignments": assignments, "department_changes": department_changes}

"""Ticket endpoints (readmes/README-ticket-actions-api.md).

Views stay thin. For an action on one Ticket they follow the documented order of checks
(readmes/README-api-conventions.md §3): authentication (401), visibility (404 from the scoped
queryset), action permission (403 from the permission classes), request validation (400), and
finally the service, which re-checks under a row lock and may answer 409.
"""

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.tickets import selectors, services
from apps.tickets.exceptions import InvalidTicketTransition
from apps.tickets.models import Ticket
from apps.tickets.pagination import ActivityFeedPagination, TicketListPagination
from apps.tickets.permissions import CanCreateTickets, CanResolveTicket, IsAssignedWorker, IsCurrentDepartmentPoc
from apps.tickets.serializers import (
    ActivityItemSerializer,
    ActivityQuerySerializer,
    AddCommentSerializer,
    AssignWorkerResponseSerializer,
    AssignWorkerSerializer,
    ChangeDepartmentResponseSerializer,
    ChangeDepartmentSerializer,
    FilterOptionsSerializer,
    MarkResolvedResponseSerializer,
    SubmitAssessmentResponseSerializer,
    SubmitAssessmentSerializer,
    TicketCreateSerializer,
    TicketDetailSerializer,
    TicketHistorySerializer,
    TicketListQuerySerializer,
    TicketListSerializer,
    UserSummarySerializer,
    build_feed_row_for_comment,
)
from config.api_helpers import parse_id, results_response

# Extra permission classes per action, on top of IsAuthenticated. The object-level ones run
# when get_object() resolves the Ticket, so a Ticket the user cannot see is a 404 before any 403.
PERMISSIONS_BY_ACTION: dict[str, list[type[BasePermission]]] = {
    "create": [CanCreateTickets],
    "eligible_workers": [IsCurrentDepartmentPoc],
    "assign_worker": [IsCurrentDepartmentPoc],
    "change_department": [IsCurrentDepartmentPoc],
    "submit_assessment": [IsAssignedWorker],
    "mark_resolved": [CanResolveTicket],
}

SERIALIZERS_BY_ACTION: dict[str, type[BaseSerializer]] = {
    "list": TicketListSerializer,
    "retrieve": TicketDetailSerializer,
    "create": TicketCreateSerializer,
}


class TicketViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Listing, detail, creation, and explicit action endpoints. There is no generic update or delete."""

    pagination_class = TicketListPagination
    # No OPTIONS introspection: DRF's metadata response asks for a serializer for every action.
    metadata_class = None
    # Matches any ID text so a malformed one reaches parse_id and answers 400, not a routing 404.
    lookup_value_regex = "[^/]+"

    def get_permissions(self) -> list[BasePermission]:
        extra_permissions = PERMISSIONS_BY_ACTION.get(self.action, [])
        return [IsAuthenticated(), *(permission() for permission in extra_permissions)]

    def get_serializer_class(self) -> type[BaseSerializer]:
        return SERIALIZERS_BY_ACTION[self.action]

    def get_queryset(self):
        user = self.request.user
        if self.action == "list":
            query = TicketListQuerySerializer(data=self.request.query_params)
            query.is_valid(raise_exception=True)
            return selectors.get_ticket_list(user, **query.validated_data)
        if self.action == "retrieve":
            return selectors.get_ticket_detail_queryset(user)
        # Actions only need what their permission checks read.
        return selectors.get_visible_tickets(user).select_related("current_department", "client_office")

    def get_object(self) -> Ticket:
        ticket_id = parse_id(self.kwargs[self.lookup_field], "ticket_id")
        ticket: Ticket = get_object_or_404(self.get_queryset(), pk=ticket_id)
        self.check_object_permissions(self.request, ticket)
        return ticket

    def create(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = services.create_ticket(creator=request.user, **serializer.validated_data)
        created_ticket = selectors.get_ticket_detail_queryset(request.user).get(pk=ticket.pk)
        response_serializer = TicketDetailSerializer(created_ticket, context=self.get_serializer_context())
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="filter-options")
    def filter_options(self, request: Request) -> Response:
        return Response(FilterOptionsSerializer(selectors.get_filter_options(request.user)).data)

    @action(detail=True, methods=["get"], url_path="eligible-workers")
    def eligible_workers(self, request: Request, pk: str) -> Response:
        ticket = self.get_object()
        if not ticket.is_awaiting_worker_assignment:
            raise InvalidTicketTransition("The ticket is not awaiting worker assignment.")
        return results_response(UserSummarySerializer, selectors.get_eligible_workers(ticket))

    @action(detail=True, methods=["post"], url_path="assign-worker")
    def assign_worker(self, request: Request, pk: str) -> Response:
        ticket = self.get_object()
        serializer = AssignWorkerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = services.assign_worker(
            ticket_id=ticket.id, actor=request.user, worker_id=serializer.validated_data["worker_id"]
        )
        return Response(AssignWorkerResponseSerializer(assignment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="change-department")
    def change_department(self, request: Request, pk: str) -> Response:
        ticket = self.get_object()
        serializer = ChangeDepartmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_ticket = services.change_department(ticket_id=ticket.id, actor=request.user, **serializer.validated_data)
        return Response(ChangeDepartmentResponseSerializer(updated_ticket).data)

    @action(detail=True, methods=["post"], url_path="submit-assessment")
    def submit_assessment(self, request: Request, pk: str) -> Response:
        ticket = self.get_object()
        serializer = SubmitAssessmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assessment = services.submit_assessment(
            ticket_id=ticket.id, actor=request.user, outcome=serializer.validated_data["outcome"]
        )
        return Response(SubmitAssessmentResponseSerializer(assessment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="mark-resolved")
    def mark_resolved(self, request: Request, pk: str) -> Response:
        ticket = self.get_object()
        closed_ticket = services.mark_ticket_resolved(ticket_id=ticket.id, actor=request.user)
        return Response(MarkResolvedResponseSerializer(closed_ticket).data)

    @action(detail=True, methods=["get"])
    def activities(self, request: Request, pk: str) -> Response:
        ticket = self.get_object()
        query = ActivityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        feed = selectors.get_activity_feed(ticket, query.validated_data["type"])
        paginator = ActivityFeedPagination()
        page = paginator.paginate_queryset(feed, request, view=self)
        actor_ids = {row["item_actor_id"] for row in page if row["item_actor_id"] is not None}
        items = ActivityItemSerializer(page, many=True, context={"actors": selectors.get_feed_actors(actor_ids)})
        return paginator.get_paginated_response(items.data)

    @action(detail=True, methods=["get"])
    def history(self, request: Request, pk: str) -> Response:
        ticket = self.get_object()
        return Response(TicketHistorySerializer(selectors.get_ticket_history(ticket)).data)

    @action(detail=True, methods=["post"])
    def comments(self, request: Request, pk: str) -> Response:
        ticket = self.get_object()
        serializer = AddCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = services.add_ticket_comment(ticket=ticket, author=request.user, body=serializer.validated_data["body"])
        feed_row = build_feed_row_for_comment(comment)
        item = ActivityItemSerializer(feed_row, context={"actors": {request.user.id: request.user}})
        return Response(item.data, status=status.HTTP_201_CREATED)

"""Read-only reference-data endpoints (readmes/README-reference-data-apis.md §3).

Every view uses the project defaults: a valid Bearer token is required.
"""

from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations import selectors
from apps.organizations.models import Client, ClientOffice
from apps.organizations.serializers import (
    ClientOfficeSerializer,
    IdNameSerializer,
    IssueSerializer,
    QuickIssueSerializer,
)
from config.api_helpers import parse_id, results_response


def get_mapped_client_or_404(request: Request, raw_client_id: str) -> Client:
    """Resolve a Client from the URL; one the user is not mapped to looks like it does not exist."""
    client_id = parse_id(raw_client_id, "client_id")
    return get_object_or_404(selectors.get_user_clients(request.user), pk=client_id)


class MyClientsView(APIView):
    def get(self, request: Request) -> Response:
        return results_response(IdNameSerializer, selectors.get_user_clients(request.user))


class ClientOfficesView(APIView):
    def get(self, request: Request, client_id: str) -> Response:
        client = get_mapped_client_or_404(request, client_id)
        return results_response(ClientOfficeSerializer, selectors.get_client_offices(request.user, client.id))


class ClientQuickIssuesView(APIView):
    def get(self, request: Request, client_id: str) -> Response:
        client = get_mapped_client_or_404(request, client_id)
        return results_response(QuickIssueSerializer, selectors.get_quick_issues(client.id))


class OfficeFloorsView(APIView):
    def get(self, request: Request, client_office_id: str) -> Response:
        office_id = parse_id(client_office_id, "client_office_id")
        office: ClientOffice = get_object_or_404(selectors.get_authorized_offices(request.user), pk=office_id)
        return results_response(IdNameSerializer, selectors.get_office_floors(office))


class DepartmentsView(APIView):
    def get(self, request: Request) -> Response:
        return results_response(IdNameSerializer, selectors.get_active_departments())


class IssuesView(APIView):
    def get(self, request: Request) -> Response:
        search_text = request.query_params.get("search", "").strip()
        raw_department_id = request.query_params.get("department_id")
        department_id = parse_id(raw_department_id, "department_id") if raw_department_id is not None else None
        return results_response(IssueSerializer, selectors.search_issues(search_text, department_id))

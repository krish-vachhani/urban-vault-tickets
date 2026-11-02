"""Health-check endpoint used by Docker Compose and load balancers."""

import logging

from django.db import DatabaseError, connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """Report whether the API process is running and can reach PostgreSQL."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        if not self._database_is_reachable():
            return Response(
                {"status": "unavailable", "database": "unreachable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"status": "ok", "database": "ok"})

    @staticmethod
    def _database_is_reachable() -> bool:
        try:
            connection.ensure_connection()
        except DatabaseError:
            logger.warning("Health check could not connect to the database.")
            return False
        return True

"""Explicit CSRF enforcement for the cookie-based authentication endpoints.

DRF views are exempt from Django's CSRF middleware, so login, refresh and logout
check the token themselves (readmes/README-authentication.md §4.3).
"""

from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

CSRF_FAILURE_MESSAGE = "CSRF verification failed."


def enforce_csrf(request: Request) -> None:
    """Raise PermissionDenied (403) unless an unsafe request carries a valid X-CSRFToken."""

    def unused_get_response(request):
        raise AssertionError("The CSRF check never calls the next view.")

    csrf_check = CsrfViewMiddleware(unused_get_response)
    csrf_check.process_request(request)
    failure_reason = csrf_check.process_view(request, None, (), {})
    if failure_reason is not None:
        # The reason is not returned to the client; it only says which check failed.
        raise PermissionDenied(CSRF_FAILURE_MESSAGE)


class CsrfProtectedAuthView(APIView):
    """Base for login, refresh and logout: public, no Bearer check, CSRF always enforced."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def initial(self, request: Request, *args, **kwargs) -> None:
        super().initial(request, *args, **kwargs)
        enforce_csrf(request)

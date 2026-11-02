from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import services
from apps.accounts.csrf import CsrfProtectedAuthView
from apps.accounts.refresh_cookie import clear_refresh_cookie, read_refresh_cookie, set_refresh_cookie
from apps.accounts.serializers import CurrentUserSerializer, LoginRequestSerializer


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfTokenView(APIView):
    """Set Django's CSRF cookie and return the token for the X-CSRFToken header."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"csrf_token": get_token(request)})


class LoginView(CsrfProtectedAuthView):
    def post(self, request: Request) -> Response:
        credentials = LoginRequestSerializer(data=request.data)
        credentials.is_valid(raise_exception=True)
        user = services.authenticate_credentials(**credentials.validated_data)
        token_pair = services.issue_token_pair(user)

        response = Response({"access": token_pair.access, "user": CurrentUserSerializer(user).data})
        set_refresh_cookie(response, token_pair.refresh)
        return response


class RefreshView(CsrfProtectedAuthView):
    def post(self, request: Request) -> Response:
        token_pair = services.rotate_refresh_token(read_refresh_cookie(request))

        response = Response({"access": token_pair.access})
        set_refresh_cookie(response, token_pair.refresh)
        return response


class LogoutView(CsrfProtectedAuthView):
    def post(self, request: Request) -> Response:
        services.revoke_refresh_token(read_refresh_cookie(request))

        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


class CurrentUserView(APIView):
    """Uses the project defaults: Bearer access token required."""

    def get(self, request: Request) -> Response:
        return Response(CurrentUserSerializer(request.user).data)

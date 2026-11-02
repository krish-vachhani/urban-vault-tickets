"""Setting and clearing the HttpOnly refresh-token cookie.

Cookie attributes: readmes/README-authentication.md §4.2. The cookie is host-only
(no Domain) and limited to the auth endpoints by its Path.
"""

from django.conf import settings
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.settings import api_settings

REFRESH_COOKIE_SAMESITE = "Lax"


def read_refresh_cookie(request: Request) -> str | None:
    return request.COOKIES.get(settings.REFRESH_COOKIE_NAME)


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=int(api_settings.REFRESH_TOKEN_LIFETIME.total_seconds()),
        path=settings.REFRESH_COOKIE_PATH,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=REFRESH_COOKIE_SAMESITE,
    )


def clear_refresh_cookie(response: Response) -> None:
    # The path and SameSite must match the attributes used when the cookie was set.
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        samesite=REFRESH_COOKIE_SAMESITE,
    )

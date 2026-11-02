"""Shared setup for the authentication tests."""

from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole

CSRF_URL = "/api/v1/auth/csrf/"
LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"

TEST_PASSWORD = "correct-horse-battery"


def create_user_with_password(role: str = UserRole.CLIENT, email: str = "login-user@example.test") -> User:
    return User.objects.create_user(email=email, password=TEST_PASSWORD, name="Login User", role=role)


def create_csrf_enforcing_client() -> APIClient:
    """A client that, like a browser, is not exempt from CSRF checks."""
    return APIClient(enforce_csrf_checks=True)


def fetch_csrf_headers(client: APIClient) -> dict[str, str]:
    """Call the CSRF endpoint (which sets the cookie) and return the matching header."""
    token = client.get(CSRF_URL).json()["csrf_token"]
    return {"HTTP_X_CSRFTOKEN": token}


def login(client: APIClient, email: str, password: str = TEST_PASSWORD):
    return client.post(LOGIN_URL, {"email": email, "password": password}, format="json", **fetch_csrf_headers(client))

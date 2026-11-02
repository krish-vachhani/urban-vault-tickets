from django.conf import settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.helpers import (
    CSRF_URL,
    LOGIN_URL,
    LOGOUT_URL,
    REFRESH_URL,
    TEST_PASSWORD,
    create_csrf_enforcing_client,
    create_user_with_password,
    fetch_csrf_headers,
    login,
)

COOKIE_NAME = settings.REFRESH_COOKIE_NAME
INVALID_CSRF_TOKEN = "x" * 64


class CsrfTokenEndpointTests(APITestCase):
    def test_endpoint_sets_the_cookie_and_returns_a_token(self) -> None:
        response = create_csrf_enforcing_client().get(CSRF_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["csrf_token"])
        self.assertIn("csrftoken", response.cookies)


class CsrfProtectionTests(APITestCase):
    """Login, refresh and logout must all reject a missing or invalid CSRF token."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = create_user_with_password()

    def setUp(self) -> None:
        self.client = create_csrf_enforcing_client()
        # A real session gives refresh and logout a valid cookie, so only the CSRF token can fail them.
        login(self.client, self.user.email)
        self.login_body = {"email": self.user.email, "password": TEST_PASSWORD}
        self.endpoints = {
            "login": (LOGIN_URL, self.login_body),
            "refresh": (REFRESH_URL, None),
            "logout": (LOGOUT_URL, None),
        }

    def post(self, url: str, body: dict | None, **headers):
        return self.client.post(url, body, format="json", **headers)

    def assert_csrf_rejected(self, response) -> None:
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["error"]["code"], "PERMISSION_DENIED")
        self.assertEqual(response.json()["error"]["details"], {})

    def test_missing_token_is_rejected(self) -> None:
        for name, (url, body) in self.endpoints.items():
            with self.subTest(endpoint=name):
                self.assert_csrf_rejected(self.post(url, body))

    def test_invalid_token_is_rejected(self) -> None:
        for name, (url, body) in self.endpoints.items():
            with self.subTest(endpoint=name):
                self.assert_csrf_rejected(self.post(url, body, HTTP_X_CSRFTOKEN=INVALID_CSRF_TOKEN))

    def test_valid_token_is_accepted(self) -> None:
        for name, (url, body) in self.endpoints.items():
            with self.subTest(endpoint=name):
                response = self.post(url, body, **fetch_csrf_headers(self.client))

                self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT))
                # Logout clears the cookie, so restore a session for the next endpoint.
                login(self.client, self.user.email)

    def test_rejected_login_issues_no_refresh_cookie(self) -> None:
        client = create_csrf_enforcing_client()

        response = client.post(LOGIN_URL, self.login_body, format="json")

        self.assertNotIn(COOKIE_NAME, response.cookies)

    def test_rejected_refresh_does_not_rotate_the_token(self) -> None:
        token_before = self.client.cookies[COOKIE_NAME].value

        self.assert_csrf_rejected(self.post(REFRESH_URL, None))

        self.assertFalse(BlacklistedToken.objects.filter(token__jti=RefreshToken(token_before)["jti"]).exists())

    def test_rejected_logout_does_not_revoke_the_token(self) -> None:
        token_before = self.client.cookies[COOKIE_NAME].value

        self.assert_csrf_rejected(self.post(LOGOUT_URL, None))

        self.assertFalse(BlacklistedToken.objects.filter(token__jti=RefreshToken(token_before)["jti"]).exists())

from datetime import timedelta

from django.conf import settings
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.models import UserRole
from apps.accounts.tests.helpers import (
    LOGIN_URL,
    LOGOUT_URL,
    ME_URL,
    REFRESH_URL,
    create_csrf_enforcing_client,
    create_user_with_password,
    fetch_csrf_headers,
    login,
)
from apps.organizations.models import Department

COOKIE_NAME = settings.REFRESH_COOKIE_NAME


def assert_error_envelope(test: APITestCase, response, status_code: int, code: str) -> None:
    test.assertEqual(response.status_code, status_code)
    test.assertEqual(response.json()["error"]["code"], code)


class LoginTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = create_user_with_password()

    def setUp(self) -> None:
        self.client = create_csrf_enforcing_client()

    def test_valid_credentials_return_access_token_and_user(self) -> None:
        response = login(self.client, self.user.email)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(AccessToken(body["access"])["user_id"], str(self.user.id))
        self.assertEqual(body["user"]["email"], self.user.email)
        self.assertEqual(body["user"]["role"], UserRole.CLIENT)

    def test_refresh_token_is_only_in_the_http_only_cookie(self) -> None:
        response = login(self.client, self.user.email)

        self.assertNotIn("refresh", response.json())
        cookie = response.cookies[COOKIE_NAME]
        self.assertTrue(cookie.value)
        self.assertNotIn(cookie.value, response.content.decode())
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie["path"], "/api/v1/auth/")
        self.assertEqual(cookie["domain"], "")
        self.assertEqual(int(cookie["max-age"]), 24 * 60 * 60)

    @override_settings(REFRESH_COOKIE_SECURE=True)
    def test_refresh_cookie_is_secure_when_configured(self) -> None:
        response = login(self.client, self.user.email)

        self.assertTrue(response.cookies[COOKIE_NAME]["secure"])

    def test_access_token_carries_no_role_claim(self) -> None:
        access = login(self.client, self.user.email).json()["access"]

        self.assertNotIn("role", AccessToken(access))

    def test_email_is_case_insensitive(self) -> None:
        response = login(self.client, "  Login-User@Example.TEST ")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_every_role_can_log_in(self) -> None:
        for role in UserRole.values:
            with self.subTest(role=role):
                user = create_user_with_password(role, email=f"{role.lower()}@example.test")
                if role == UserRole.DEPARTMENT_POC:
                    Department.objects.create(name="Test Department", poc_user=user)
                response = login(create_csrf_enforcing_client(), user.email)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.json()["user"]["role"], role)

    def test_wrong_password_and_unknown_email_get_the_same_generic_401(self) -> None:
        wrong_password = login(self.client, self.user.email, password="wrong-password")
        unknown_email = login(self.client, "nobody@example.test")

        assert_error_envelope(self, wrong_password, status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")
        self.assertEqual(wrong_password.json(), unknown_email.json())
        self.assertNotIn(COOKIE_NAME, wrong_password.cookies)

    def test_disabled_user_cannot_log_in(self) -> None:
        self.user.is_active = False
        self.user.save()

        response = login(self.client, self.user.email)

        assert_error_envelope(self, response, status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")

    def test_missing_fields_return_validation_error(self) -> None:
        response = self.client.post(LOGIN_URL, {}, format="json", **fetch_csrf_headers(self.client))

        assert_error_envelope(self, response, status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR")
        self.assertEqual(set(response.json()["error"]["details"]), {"email", "password"})


class RefreshTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = create_user_with_password()

    def setUp(self) -> None:
        self.client = create_csrf_enforcing_client()
        login(self.client, self.user.email)
        self.first_refresh_token = self.client.cookies[COOKIE_NAME].value

    def post_refresh(self, client: APIClient | None = None):
        client = client or self.client
        return client.post(REFRESH_URL, **fetch_csrf_headers(client))

    def test_refresh_returns_a_new_access_token_that_works(self) -> None:
        response = self.post_refresh()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.json()), {"access"})
        me_response = APIClient().get(ME_URL, HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)

    def test_refresh_rotates_the_cookie_and_blacklists_the_previous_token(self) -> None:
        response = self.post_refresh()

        new_refresh_token = response.cookies[COOKIE_NAME].value
        self.assertNotEqual(new_refresh_token, self.first_refresh_token)
        self.assertTrue(response.cookies[COOKIE_NAME]["httponly"])
        previous_jti = RefreshToken(self.first_refresh_token, verify=False)["jti"]
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=previous_jti).exists())

    def test_previous_refresh_token_cannot_be_reused_after_rotation(self) -> None:
        self.post_refresh()
        self.client.cookies[COOKIE_NAME] = self.first_refresh_token

        response = self.post_refresh()

        assert_error_envelope(self, response, status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")
        self.assertNotIn("access", response.json())

    def test_missing_cookie_is_rejected(self) -> None:
        del self.client.cookies[COOKIE_NAME]

        assert_error_envelope(self, self.post_refresh(), status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")

    def test_malformed_cookie_is_rejected(self) -> None:
        self.client.cookies[COOKIE_NAME] = "not-a-jwt"

        assert_error_envelope(self, self.post_refresh(), status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")

    def test_expired_refresh_token_is_rejected(self) -> None:
        expired_token = RefreshToken.for_user(self.user)
        expired_token.set_exp(from_time=timezone.now() - timedelta(days=2))
        self.client.cookies[COOKIE_NAME] = str(expired_token)

        assert_error_envelope(self, self.post_refresh(), status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")

    def test_access_token_is_not_accepted_as_a_refresh_token(self) -> None:
        self.client.cookies[COOKIE_NAME] = str(RefreshToken.for_user(self.user).access_token)

        assert_error_envelope(self, self.post_refresh(), status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")

    def test_refresh_token_in_the_request_body_is_ignored(self) -> None:
        del self.client.cookies[COOKIE_NAME]

        response = self.client.post(
            REFRESH_URL, {"refresh": self.first_refresh_token}, format="json", **fetch_csrf_headers(self.client)
        )

        assert_error_envelope(self, response, status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")

    def test_disabled_user_cannot_refresh(self) -> None:
        self.user.is_active = False
        self.user.save()

        assert_error_envelope(self, self.post_refresh(), status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")


class LogoutTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = create_user_with_password()

    def setUp(self) -> None:
        self.client = create_csrf_enforcing_client()
        login(self.client, self.user.email)
        self.refresh_token = self.client.cookies[COOKIE_NAME].value

    def post_logout(self):
        return self.client.post(LOGOUT_URL, **fetch_csrf_headers(self.client))

    def test_logout_blacklists_the_refresh_token_and_clears_the_cookie(self) -> None:
        response = self.post_logout()

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        cookie = response.cookies[COOKIE_NAME]
        self.assertEqual(cookie.value, "")
        self.assertEqual(cookie["path"], "/api/v1/auth/")
        self.assertEqual(int(cookie["max-age"]), 0)
        jti = RefreshToken(self.refresh_token, verify=False)["jti"]
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=jti).exists())

    def test_refresh_fails_after_logout(self) -> None:
        self.post_logout()
        self.client.cookies[COOKIE_NAME] = self.refresh_token

        response = self.client.post(REFRESH_URL, **fetch_csrf_headers(self.client))

        assert_error_envelope(self, response, status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")

    def test_logout_works_without_an_access_token(self) -> None:
        # setUp never sent a Bearer header, which models a user whose access token expired.
        self.assertEqual(self.post_logout().status_code, status.HTTP_204_NO_CONTENT)

    def test_logout_without_a_valid_refresh_cookie_still_clears_the_cookie(self) -> None:
        for cookie_value in (None, "not-a-jwt"):
            with self.subTest(cookie_value=cookie_value):
                if cookie_value is None:
                    del self.client.cookies[COOKIE_NAME]
                else:
                    self.client.cookies[COOKIE_NAME] = cookie_value

                response = self.post_logout()

                self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
                self.assertEqual(response.cookies[COOKIE_NAME].value, "")

    def test_logging_out_twice_is_harmless(self) -> None:
        self.post_logout()

        self.assertEqual(self.post_logout().status_code, status.HTTP_204_NO_CONTENT)

    def test_account_switch_logs_in_as_the_next_user(self) -> None:
        other_user = create_user_with_password(UserRole.WORKER, email="other@example.test")
        self.post_logout()

        response = login(self.client, other_user.email)

        self.assertEqual(response.json()["user"]["email"], other_user.email)
        self.assertNotEqual(response.cookies[COOKIE_NAME].value, self.refresh_token)


class BearerAuthenticationTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = create_user_with_password()

    def get_me(self, authorization: str | None = None):
        headers = {"HTTP_AUTHORIZATION": authorization} if authorization else {}
        return self.client.get(ME_URL, **headers)

    def test_real_access_token_from_login_authenticates(self) -> None:
        access = login(create_csrf_enforcing_client(), self.user.email).json()["access"]

        response = self.get_me(f"Bearer {access}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["id"], self.user.id)

    def test_missing_token_returns_401_envelope(self) -> None:
        assert_error_envelope(self, self.get_me(), status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")

    def test_invalid_token_returns_401_envelope(self) -> None:
        assert_error_envelope(self, self.get_me("Bearer not-a-jwt"), status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")

    def test_expired_token_returns_401_envelope(self) -> None:
        token = AccessToken.for_user(self.user)
        token.set_exp(from_time=timezone.now() - timedelta(hours=1))

        assert_error_envelope(self, self.get_me(f"Bearer {token}"), status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")

    def test_refresh_token_is_not_accepted_as_a_bearer_token(self) -> None:
        refresh_token = RefreshToken.for_user(self.user)

        response = self.get_me(f"Bearer {refresh_token}")

        assert_error_envelope(self, response, status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")

    def test_refresh_cookie_alone_does_not_authenticate_an_api_request(self) -> None:
        client = create_csrf_enforcing_client()
        login(client, self.user.email)

        response = client.get(ME_URL)

        assert_error_envelope(self, response, status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")

    def test_disabled_user_with_a_valid_access_token_is_rejected(self) -> None:
        access = str(AccessToken.for_user(self.user))
        self.user.is_active = False
        self.user.save()

        assert_error_envelope(self, self.get_me(f"Bearer {access}"), status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED")

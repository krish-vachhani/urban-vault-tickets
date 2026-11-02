"""Token and credential operations for authentication.

SimpleJWT does the token work; these functions only wrap it so views stay thin.
"""

from dataclasses import dataclass

from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User, UserManager

INVALID_CREDENTIALS_MESSAGE = "Invalid email or password."


@dataclass(frozen=True)
class TokenPair:
    """A freshly issued access token and the refresh token that belongs in the cookie."""

    access: str
    refresh: str


def authenticate_credentials(email: str, password: str) -> User:
    """Return the active user for these credentials or raise a generic 401.

    The message never says whether the email or the password was wrong. Django's
    default backend also rejects inactive accounts.
    """
    user = authenticate(username=UserManager.normalize_login_email(email), password=password)
    if user is None:
        raise AuthenticationFailed(INVALID_CREDENTIALS_MESSAGE)
    return user


def issue_token_pair(user: User) -> TokenPair:
    refresh_token = RefreshToken.for_user(user)
    return TokenPair(access=str(refresh_token.access_token), refresh=str(refresh_token))


def rotate_refresh_token(refresh_token: str | None) -> TokenPair:
    """Exchange a valid refresh token for a new pair; the presented one is blacklisted.

    Missing, malformed, expired, blacklisted and disabled-user tokens all raise the same 401.
    """
    if not refresh_token:
        raise InvalidToken()
    serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
    try:
        serializer.is_valid(raise_exception=True)
    except (TokenError, User.DoesNotExist) as error:
        raise InvalidToken() from error
    return TokenPair(access=serializer.validated_data["access"], refresh=serializer.validated_data["refresh"])


def revoke_refresh_token(refresh_token: str | None) -> None:
    """Blacklist the refresh token when it is still valid; ignore any that is not.

    Logout must succeed for a missing, expired or already-revoked token so the
    browser cookie is always cleared.
    """
    if not refresh_token:
        return
    try:
        RefreshToken(refresh_token).blacklist()
    except TokenError:
        pass

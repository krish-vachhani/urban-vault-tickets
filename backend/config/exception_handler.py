"""The single DRF exception handler that produces the API error envelope.

Envelope and error codes: readmes/README-api-conventions.md §2 and §3.
"""

import logging
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

GENERIC_AUTHENTICATION_MESSAGE = "Authentication credentials were missing or invalid."
GENERIC_NOT_FOUND_MESSAGE = "Not found."
GENERIC_SERVER_ERROR_MESSAGE = "An unexpected error occurred."
VALIDATION_ERROR_MESSAGE = "The request contains invalid data."


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    if isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    if isinstance(exc, exceptions.ValidationError):
        return _error_response(
            status.HTTP_400_BAD_REQUEST,
            "VALIDATION_ERROR",
            VALIDATION_ERROR_MESSAGE,
            details=_build_validation_details(exc.detail),
        )
    if isinstance(exc, exceptions.ParseError):
        return _error_response(status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", "Malformed request body.")
    # DRF turns authentication errors into 403 when a view has no authentication class
    # (login, refresh, logout), so the 401 is set here instead of read from the exception.
    if isinstance(exc, exceptions.AuthenticationFailed | exceptions.NotAuthenticated):
        return _error_response(status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED", _get_authentication_message(exc))
    if isinstance(exc, exceptions.PermissionDenied):
        return _error_response(status.HTTP_403_FORBIDDEN, "PERMISSION_DENIED", str(exc.detail))
    if isinstance(exc, Http404 | exceptions.NotFound):
        return _error_response(status.HTTP_404_NOT_FOUND, "NOT_FOUND", GENERIC_NOT_FOUND_MESSAGE)

    # Remaining DRF errors (405 method not allowed, 415 unsupported media type, ...)
    # keep their own status; DRF also adds headers such as Allow.
    drf_response = drf_exception_handler(exc, context)
    if drf_response is not None:
        error_code = exc.default_code.upper()
        return _error_response(drf_response.status_code, error_code, str(exc.detail), headers=drf_response.headers)

    logger.exception("Unhandled exception while serving the request.", exc_info=exc)
    return _error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", GENERIC_SERVER_ERROR_MESSAGE)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    body = {"error": {"code": code, "message": message, "details": details or {}}}
    return Response(body, status=status_code, headers=headers)


def _get_authentication_message(exc: exceptions.APIException) -> str:
    """Use the view's own message (e.g. "Invalid email or password.") but never a token error dict."""
    if isinstance(exc.detail, str):
        return str(exc.detail)
    return GENERIC_AUTHENTICATION_MESSAGE


def _build_validation_details(detail: Any) -> dict[str, Any]:
    """Return field name -> list of messages; object-level errors go under non_field_errors."""
    if isinstance(detail, dict):
        return {field: _stringify_errors(messages) for field, messages in detail.items()}
    return {"non_field_errors": _stringify_errors(detail)}


def _stringify_errors(detail: Any) -> Any:
    """Convert DRF ErrorDetail objects to plain strings, keeping lists and nested dicts."""
    if isinstance(detail, dict):
        return {key: _stringify_errors(value) for key, value in detail.items()}
    if isinstance(detail, list):
        return [_stringify_errors(item) for item in detail]
    return str(detail)

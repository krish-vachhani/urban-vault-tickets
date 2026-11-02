"""Small helpers for reading configuration from environment variables.

Settings fail fast at startup when a required variable is missing or invalid,
so a misconfigured container stops immediately with a clear message instead
of failing later on the first request.
"""

import os

from django.core.exceptions import ImproperlyConfigured

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def get_required_env(name: str) -> str:
    """Return a non-empty environment variable or stop with a clear error."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Required environment variable {name} is not set.")
    return value


def get_optional_env(name: str, default: str) -> str:
    """Return an environment variable, or the default when it is missing or empty."""
    value = os.environ.get(name, "").strip()
    return value or default


def get_bool_env(name: str, default: bool) -> bool:
    """Parse a boolean flag such as DEBUG=True or COOKIE_SECURE=false."""
    raw_value = os.environ.get(name, "").strip().lower()
    if not raw_value:
        return default
    if raw_value in TRUE_VALUES:
        return True
    if raw_value in FALSE_VALUES:
        return False
    raise ImproperlyConfigured(f"Environment variable {name} must be true or false, got {raw_value!r}.")


def get_int_env(name: str, default: int) -> int:
    """Parse an integer setting such as DB_PORT=5432."""
    raw_value = os.environ.get(name, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError as error:
        raise ImproperlyConfigured(f"Environment variable {name} must be an integer, got {raw_value!r}.") from error


def get_list_env(name: str, default: list[str]) -> list[str]:
    """Parse a comma-separated list such as ALLOWED_HOSTS=localhost,backend."""
    raw_value = os.environ.get(name, "").strip()
    if not raw_value:
        return default
    return [item.strip() for item in raw_value.split(",") if item.strip()]

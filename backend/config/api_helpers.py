"""Small helpers shared by the read-only reference-data views."""

from typing import Any

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer


def parse_id(raw_value: str, field_name: str) -> int:
    """Turn a URL or query-string ID into an int, or raise 400 for a malformed one.

    A well-formed ID that matches nothing is not an error here: the caller decides
    between an empty result and 404 (readmes/README-api-conventions.md §4 and §7).
    """
    if not raw_value.isascii() or not raw_value.isdecimal():
        raise ValidationError({field_name: ["Must be a positive whole number."]})
    return int(raw_value)


def results_response(serializer_class: type[BaseSerializer], items: Any) -> Response:
    """Wrap a reference-data list in the unpaginated {"results": [...]} shape."""
    return Response({"results": serializer_class(items, many=True).data})

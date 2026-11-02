"""Page-number pagination that rejects bad page parameters instead of silently correcting them.

DRF's default class clamps an oversized page_size and answers 404 for a bad page. The API
conventions require 400 VALIDATION_ERROR for page=0, page_size=500, and the like
(readmes/README-api-conventions.md §7).
"""

from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request

MIN_PAGE_SIZE = 1


def _parse_whole_number(raw_value: str, parameter: str, minimum: int, maximum: int | None = None) -> int:
    if not raw_value.isascii() or not raw_value.isdecimal() or int(raw_value) < minimum:
        raise ValidationError({parameter: [f"Must be a whole number of at least {minimum}."]})
    value = int(raw_value)
    if maximum is not None and value > maximum:
        raise ValidationError({parameter: [f"Must be at most {maximum}."]})
    return value


class StrictPageNumberPagination(PageNumberPagination):
    page_size_query_param = "page_size"

    def get_page_size(self, request: Request) -> int:
        raw_page_size = request.query_params.get(self.page_size_query_param)
        if raw_page_size is None:
            return self.page_size
        return _parse_whole_number(raw_page_size, self.page_size_query_param, MIN_PAGE_SIZE, self.max_page_size)

    def paginate_queryset(self, queryset, request: Request, view=None):
        raw_page = request.query_params.get(self.page_query_param)
        if raw_page is not None:
            _parse_whole_number(raw_page, self.page_query_param, minimum=1)
        try:
            return super().paginate_queryset(queryset, request, view)
        except NotFound:
            raise ValidationError({self.page_query_param: ["That page does not exist."]}) from None


class TicketListPagination(StrictPageNumberPagination):
    page_size = 10
    max_page_size = 50


class ActivityFeedPagination(StrictPageNumberPagination):
    page_size = 20
    max_page_size = 50

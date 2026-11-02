from rest_framework import status
from rest_framework.exceptions import APIException


class InvalidTicketTransition(APIException):
    """The user may act on the Ticket, but its stage or status does not allow it (409)."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "The ticket's current state does not allow this action."
    # The exception handler upper-cases this into the INVALID_TICKET_TRANSITION error code.
    default_code = "invalid_ticket_transition"

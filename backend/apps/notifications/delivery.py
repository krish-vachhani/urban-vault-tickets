"""Simulated notification delivery.

The assignment needs no real email or SMS provider, so "delivering" a notification means
building its message and writing it to the log. The durable SENT status on the outbox row
is the observable result. Nothing here touches the network or any other irreversible
side effect, which is what makes running it twice harmless.
"""

import logging

from apps.notifications.models import NotificationEventType, NotificationOutbox

logger = logging.getLogger(__name__)

MESSAGE_TEMPLATES = {
    NotificationEventType.TICKET_ROUTED: "Ticket {ticket_number} was created and routed to your department.",
    NotificationEventType.WORKER_ASSIGNED: "You were assigned to ticket {ticket_number}.",
    NotificationEventType.DEPARTMENT_CHANGED: "Ticket {ticket_number} was forwarded to your department.",
    NotificationEventType.ASSESSMENT_SUBMITTED: "A worker submitted an assessment for ticket {ticket_number}.",
}


class DeliveryError(Exception):
    """A delivery attempt failed. The message must be safe to store and log."""


class TransientDeliveryError(DeliveryError):
    """The attempt failed for a reason that may pass, such as a provider timeout. Worth retrying."""


class PermanentDeliveryError(DeliveryError):
    """The attempt can never succeed, such as an unknown event type. Retrying would be pointless."""


def deliver_simulated_notification(outbox: NotificationOutbox) -> None:
    """Build the message for an outbox row and log it as if it had been sent."""
    if not outbox.recipient.is_active:
        raise PermanentDeliveryError("The recipient account is inactive.")

    message = build_message(outbox)
    logger.info(
        "simulated_notification_delivered outbox_id=%s recipient_id=%s message=%r",
        outbox.id,
        outbox.recipient_id,
        message,
    )


def build_message(outbox: NotificationOutbox) -> str:
    template = MESSAGE_TEMPLATES.get(outbox.event_type)
    if template is None:
        raise PermanentDeliveryError(f"No message template for event type {outbox.event_type}.")
    try:
        return template.format(**outbox.payload)
    except KeyError as error:
        raise PermanentDeliveryError(f"The payload is missing {error}.") from error

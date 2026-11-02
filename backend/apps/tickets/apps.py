from django.apps import AppConfig


class TicketsConfig(AppConfig):
    """Ticket lifecycle: creation, listing, assignment, forwarding, assessment, resolution, activity."""

    name = "apps.tickets"
    # Short label keeps model references stable, e.g. "tickets.ModelName".
    label = "tickets"
    verbose_name = "Tickets"

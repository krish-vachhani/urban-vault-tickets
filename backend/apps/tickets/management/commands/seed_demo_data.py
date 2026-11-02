"""Load the deterministic demo data described in readmes/README-seed-data.md.

Run explicitly (containers never run it automatically):

    python manage.py seed_demo_data

Safe to run repeatedly: reference data and users are refreshed in place, and
demo Tickets are created only while the database has no Tickets.
"""

import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.tickets.demo_seed.demo_tickets import seed_demo_tickets
from apps.tickets.demo_seed.reference_data import seed_reference_data
from apps.tickets.models import Ticket

PASSWORD_VARIABLE = "SEED_DEMO_PASSWORD"


class Command(BaseCommand):
    help = "Create demo users, organizations, Departments, Issues, and Tickets (safe to run repeatedly)."

    def handle(self, *args, **options) -> None:
        demo_password = os.environ.get(PASSWORD_VARIABLE, "").strip()
        if not demo_password:
            raise CommandError(f"Set {PASSWORD_VARIABLE} (see .env.example) before seeding demo accounts.")

        # One transaction: a failure part-way leaves the database exactly as it was.
        with transaction.atomic():
            seed_reference_data(demo_password)
            self.stdout.write("Demo users, organizations, Departments, and Issues are up to date.")

            if Ticket.objects.exists():
                self.stdout.write("Tickets already exist, so no demo Tickets were created.")
            else:
                created_count = seed_demo_tickets(now=timezone.now())
                self.stdout.write(f"Created {created_count} demo Tickets.")

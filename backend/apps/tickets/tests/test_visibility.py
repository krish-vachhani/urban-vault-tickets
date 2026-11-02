from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import UserRole
from apps.organizations.tests.helpers import (
    create_client,
    create_department,
    create_office,
    create_property,
    create_user,
    create_worker,
    map_user_to_client,
)
from apps.tickets.models import AssignmentEndReason, TicketAssignment
from apps.tickets.selectors import get_visible_tickets
from apps.tickets.tests.helpers import create_ticket


class TicketVisibilityTests(TestCase):
    @staticmethod
    def assign(ticket, worker, department, **fields) -> None:
        assigned_at = timezone.now() - timedelta(hours=1)
        TicketAssignment.objects.create(
            ticket=ticket, worker=worker, assigned_by=department.poc_user, assigned_at=assigned_at, **fields
        )

    def visible_ids(self, user) -> set[int]:
        return set(get_visible_tickets(user).values_list("id", flat=True))

    def test_client_sees_tickets_of_every_mapped_client_including_others_creations(self) -> None:
        client = create_client()
        user = create_user(UserRole.CLIENT)
        map_user_to_client(user, client)
        colleague_ticket = create_ticket(client_office=create_office(client))
        unrelated_ticket = create_ticket()

        visible = self.visible_ids(user)

        self.assertIn(colleague_ticket.id, visible)
        self.assertNotIn(unrelated_ticket.id, visible)

    def test_facility_manager_sees_managed_properties_only(self) -> None:
        manager = create_user(UserRole.FACILITY_MANAGER)
        managed_ticket = create_ticket(client_office=create_office(property_record=create_property(manager)))
        other_ticket = create_ticket()

        visible = self.visible_ids(manager)

        self.assertIn(managed_ticket.id, visible)
        self.assertNotIn(other_ticket.id, visible)

    def test_department_poc_sees_tickets_currently_in_their_department(self) -> None:
        department = create_department()
        forwarded_ticket = create_ticket(origin_department=department)
        other_ticket = create_ticket()
        self.assertIn(forwarded_ticket.id, self.visible_ids(department.poc_user))

        new_department = create_department()
        forwarded_ticket.current_department = new_department
        forwarded_ticket.save()

        self.assertNotIn(forwarded_ticket.id, self.visible_ids(department.poc_user))
        self.assertIn(forwarded_ticket.id, self.visible_ids(new_department.poc_user))
        self.assertNotIn(other_ticket.id, self.visible_ids(department.poc_user))

    def test_worker_sees_current_and_past_assignments_only(self) -> None:
        department = create_department()
        worker = create_worker(department)
        current_ticket = create_ticket(origin_department=department)
        past_ticket = create_ticket(origin_department=department)
        unassigned_ticket = create_ticket(origin_department=department)
        self.assign(current_ticket, worker, department)
        self.assign(
            past_ticket, worker, department, ended_at=timezone.now(), end_reason=AssignmentEndReason.REASSIGNED
        )

        visible = self.visible_ids(worker)

        self.assertIn(current_ticket.id, visible)
        self.assertIn(past_ticket.id, visible)
        self.assertNotIn(unassigned_ticket.id, visible)

    def test_creator_sees_their_ticket_after_it_is_routed_elsewhere(self) -> None:
        technical = create_department()
        it_department = create_department()
        ticket = create_ticket(created_by=technical.poc_user, origin_department=technical, current_department=it_department)

        self.assertIn(ticket.id, self.visible_ids(technical.poc_user))

    def test_visibility_never_duplicates_tickets(self) -> None:
        client = create_client()
        user = create_user(UserRole.CLIENT)
        map_user_to_client(user, client)
        create_ticket(client_office=create_office(client), created_by=user)

        self.assertEqual(get_visible_tickets(user).count(), 1)

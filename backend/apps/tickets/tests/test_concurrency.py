"""Races between real database connections.

These use TransactionTestCase so each request thread commits for real; an ordinary test
case wraps everything in one transaction and cannot show row locks at work.
"""

import threading
from collections.abc import Callable

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.exceptions import PermissionDenied

from apps.organizations.tests.helpers import create_worker
from apps.tickets import services
from apps.tickets.exceptions import InvalidTicketTransition
from apps.tickets.models import AssessmentOutcome, Ticket, TicketAssessment, TicketAssignment, TicketStatus
from apps.tickets.tests.helpers import create_scene, move_to_assessment_stage

THREAD_TIMEOUT_SECONDS = 30


def run_at_the_same_time(operations: list[Callable[[], object]]) -> list[object]:
    """Run each operation in its own thread (and so its own connection); return result or exception per operation."""
    start_together = threading.Barrier(len(operations))
    outcomes: list[object] = [None] * len(operations)

    def run(index: int, operation: Callable[[], object]) -> None:
        try:
            start_together.wait(timeout=THREAD_TIMEOUT_SECONDS)
            outcomes[index] = operation()
        except Exception as error:  # the test inspects which operations failed and why
            outcomes[index] = error
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(index, operation)) for index, operation in enumerate(operations)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=THREAD_TIMEOUT_SECONDS)
    return outcomes


class ConcurrentActionTests(TransactionTestCase):
    def test_two_pocs_assigning_different_workers_at_once_create_one_active_assignment(self) -> None:
        scene = create_scene()
        second_worker = create_worker(scene.department)

        outcomes = run_at_the_same_time(
            [
                lambda: services.assign_worker(ticket_id=scene.ticket.id, actor=scene.poc, worker_id=scene.worker.id),
                lambda: services.assign_worker(ticket_id=scene.ticket.id, actor=scene.poc, worker_id=second_worker.id),
            ]
        )

        failures = [outcome for outcome in outcomes if isinstance(outcome, Exception)]
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], InvalidTicketTransition)
        self.assertEqual(TicketAssignment.objects.filter(ticket=scene.ticket, ended_at__isnull=True).count(), 1)

    def test_a_worker_double_submitting_creates_one_assessment(self) -> None:
        scene = create_scene()
        move_to_assessment_stage(scene.ticket, scene.worker)

        outcomes = run_at_the_same_time(
            [
                lambda: services.submit_assessment(
                    ticket_id=scene.ticket.id, actor=scene.worker, outcome=AssessmentOutcome.FULLY_RESOLVED
                ),
                lambda: services.submit_assessment(
                    ticket_id=scene.ticket.id, actor=scene.worker, outcome=AssessmentOutcome.CHANGE_REQUESTED
                ),
            ]
        )

        failures = [outcome for outcome in outcomes if isinstance(outcome, Exception)]
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], InvalidTicketTransition)
        self.assertEqual(TicketAssessment.objects.filter(ticket=scene.ticket).count(), 1)

    def test_resolving_while_the_worker_submits_leaves_a_consistent_closed_ticket(self) -> None:
        scene = create_scene()
        move_to_assessment_stage(scene.ticket, scene.worker)

        outcomes = run_at_the_same_time(
            [
                lambda: services.submit_assessment(
                    ticket_id=scene.ticket.id, actor=scene.worker, outcome=AssessmentOutcome.FULLY_RESOLVED
                ),
                lambda: services.mark_ticket_resolved(ticket_id=scene.ticket.id, actor=scene.client_user),
            ]
        )

        # Either order is valid; what must hold is that nothing half-applied remains.
        for outcome in outcomes:
            if isinstance(outcome, Exception):
                self.assertIsInstance(outcome, InvalidTicketTransition | PermissionDenied)
        ticket = Ticket.objects.get(pk=scene.ticket.id)
        self.assertEqual(ticket.status, TicketStatus.CLOSED)
        self.assertEqual(TicketAssignment.objects.filter(ticket=ticket, ended_at__isnull=True).count(), 0)

    def test_two_users_resolving_at_once_close_the_ticket_only_once(self) -> None:
        scene = create_scene()

        outcomes = run_at_the_same_time(
            [
                lambda: services.mark_ticket_resolved(ticket_id=scene.ticket.id, actor=scene.client_user),
                lambda: services.mark_ticket_resolved(ticket_id=scene.ticket.id, actor=scene.colleague_client_user),
            ]
        )

        failures = [outcome for outcome in outcomes if isinstance(outcome, Exception)]
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], InvalidTicketTransition)
        self.assertEqual(scene.ticket.activities.filter(event_type="TICKET_RESOLVED").count(), 1)

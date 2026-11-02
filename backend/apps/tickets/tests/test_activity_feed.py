from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.organizations.tests.helpers import create_department, create_worker
from apps.tickets.activity import build_change
from apps.tickets.models import ActivityEventType, TicketComment
from apps.tickets.tests.helpers import create_activity, create_assignment, create_scene


def activities_url(ticket_id) -> str:
    return f"/api/v1/tickets/{ticket_id}/activities/"


def history_url(ticket_id) -> str:
    return f"/api/v1/tickets/{ticket_id}/history/"


class ActivityFeedTests(APITestCase):
    def setUp(self) -> None:
        self.scene = create_scene()
        self.ticket = self.scene.ticket
        start = timezone.now() - timedelta(hours=5)
        self.created = create_activity(
            self.ticket, actor=self.scene.client_user, created_at=start, description="created the ticket."
        )
        self.routed = create_activity(
            self.ticket,
            actor=None,
            event_type=ActivityEventType.TICKET_ROUTED,
            description="Ticket routed to the Technical department.",
            created_at=start + timedelta(minutes=1),
        )
        self.assigned = create_activity(
            self.ticket,
            actor=self.scene.poc,
            event_type=ActivityEventType.WORKER_ASSIGNED,
            description="assigned technician.",
            metadata={"change": build_change("assignee", "Unassigned", "Prakash Kumar (Technician)")},
            created_at=start + timedelta(hours=2),
        )
        self.comment = TicketComment.objects.create(
            ticket=self.ticket,
            author=self.scene.worker,
            body="Technician inspected the AC.",
            created_at=start + timedelta(hours=1),
        )

    def get_feed(self, user=None, **query):
        self.client.force_authenticate(user or self.scene.client_user)
        return self.client.get(activities_url(self.ticket.id), query)

    def test_all_combines_actions_and_comments_oldest_first(self) -> None:
        response = self.get_feed()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["count"], 4)
        self.assertEqual(
            [item["id"] for item in body["results"]],
            [f"action-{self.created.id}", f"action-{self.routed.id}", f"comment-{self.comment.id}", f"action-{self.assigned.id}"],
        )

    def test_type_filters_split_the_feed(self) -> None:
        actions = self.get_feed(type="ACTIONS").json()
        comments = self.get_feed(type="COMMENTS").json()
        everything = self.get_feed(type="ALL").json()

        self.assertEqual({item["type"] for item in actions["results"]}, {"ACTION"})
        self.assertEqual(actions["count"], 3)
        self.assertEqual([item["type"] for item in comments["results"]], ["COMMENT"])
        self.assertEqual(everything["count"], 4)

    def test_action_and_comment_items_carry_the_right_columns(self) -> None:
        results = {item["id"]: item for item in self.get_feed().json()["results"]}

        assigned = results[f"action-{self.assigned.id}"]
        self.assertEqual(assigned["type"], "ACTION")
        self.assertEqual(assigned["event_type"], "WORKER_ASSIGNED")
        self.assertEqual(assigned["description"], "assigned technician.")
        self.assertEqual(assigned["change"], {"field": "assignee", "from": "Unassigned", "to": "Prakash Kumar (Technician)"})
        self.assertIsNone(assigned["note"])
        self.assertEqual(
            assigned["actor"],
            {
                "id": self.scene.poc.id,
                "name": self.scene.poc.name,
                "role": "DEPARTMENT_POC",
                "role_label": f"{self.scene.department.name} Manager",
            },
        )
        comment = results[f"comment-{self.comment.id}"]
        self.assertEqual(comment["type"], "COMMENT")
        self.assertIsNone(comment["event_type"])
        self.assertEqual(comment["description"], "Technician inspected the AC.")
        self.assertEqual(comment["actor"]["role_label"], "Technician")
        self.assertIsNone(comment["change"])
        self.assertIsNone(comment["note"])
        self.assertIsNone(results[f"action-{self.routed.id}"]["actor"], "system events have no actor")

    def test_the_forwarding_note_is_returned_on_department_changes(self) -> None:
        forwarded = create_activity(
            self.ticket,
            actor=self.scene.poc,
            event_type=ActivityEventType.DEPARTMENT_CHANGED,
            description="changed the department.",
            metadata={"note": "Belongs to IT.", "change": build_change("department", "Technical", "IT")},
        )

        item = next(item for item in self.get_feed().json()["results"] if item["id"] == f"action-{forwarded.id}")

        self.assertEqual(item["note"], "Belongs to IT.")
        self.assertEqual(item["change"]["to"], "IT")

    def test_an_action_and_a_comment_at_the_same_instant_keep_a_stable_order(self) -> None:
        moment = timezone.now()
        action = create_activity(self.ticket, actor=self.scene.poc, created_at=moment)
        tied_comment = TicketComment.objects.create(
            ticket=self.ticket, author=self.scene.poc, body="Same time.", created_at=moment
        )

        ids = [item["id"] for item in self.get_feed().json()["results"]]

        self.assertEqual(ids[-2:], [f"action-{action.id}", f"comment-{tied_comment.id}"])

    def test_pages_are_20_by_default_with_a_maximum_of_50(self) -> None:
        for number in range(25):
            TicketComment.objects.create(ticket=self.ticket, author=self.scene.poc, body=f"Comment {number}")

        first = self.get_feed().json()
        second = self.get_feed(page=2).json()

        self.assertEqual((first["count"], len(first["results"])), (29, 20))
        self.assertEqual(len(second["results"]), 9)
        self.assertIsNotNone(first["next"])
        self.assertIsNone(second["next"])
        self.assertEqual(len(self.get_feed(page_size=50).json()["results"]), 29)
        self.assertEqual(self.get_feed(page_size=51).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.get_feed(page=0).status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_type_is_a_validation_error(self) -> None:
        response = self.get_feed(type="EVERYTHING")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("type", response.json()["error"]["details"])

    def test_every_viewer_with_visibility_sees_the_same_feed(self) -> None:
        for user in (self.scene.facility_manager, self.scene.poc):
            self.assertEqual(self.get_feed(user).json()["count"], 4)

    def test_user_without_visibility_gets_404(self) -> None:
        for user in (create_scene().client_user, create_department().poc_user, create_worker(self.scene.department)):
            with self.subTest(role=user.role):
                self.assertEqual(self.get_feed(user).status_code, status.HTTP_404_NOT_FOUND)

    def test_feed_query_count_does_not_depend_on_the_number_of_items(self) -> None:
        with CaptureQueriesContext(connection) as few_items:
            self.get_feed()
        for number in range(10):
            TicketComment.objects.create(ticket=self.ticket, author=self.scene.poc, body=f"More {number}")
        with CaptureQueriesContext(connection) as many_items:
            self.get_feed()

        self.assertEqual(len(few_items), len(many_items))


class HistoryTests(APITestCase):
    def setUp(self) -> None:
        self.scene = create_scene()
        self.ticket = self.scene.ticket

    def get_history(self, user=None):
        self.client.force_authenticate(user or self.scene.facility_manager)
        return self.client.get(history_url(self.ticket.id))

    def test_history_lists_assignments_with_the_unassigned_progression_and_department_changes(self) -> None:
        forwarded = create_activity(
            self.ticket,
            actor=self.scene.poc,
            event_type=ActivityEventType.DEPARTMENT_CHANGED,
            description="changed the department.",
            metadata={
                "note": "Belongs to IT.",
                "change": build_change("department", "Technical", "IT"),
            },
        )
        create_activity(self.ticket, actor=self.scene.poc)  # unrelated activities are not History
        first_end = timezone.now() - timedelta(hours=1)
        first = create_assignment(self.ticket, self.scene.worker, ended_at=first_end, end_reason="REASSIGNED")
        second_worker = create_worker(self.scene.department)
        second = create_assignment(self.ticket, second_worker)

        body = self.get_history().json()

        first_item, second_item = body["assignments"]
        self.assertEqual(first_item["id"], f"assignment-{first.id}")
        self.assertEqual(first_item["change"]["from"], "Unassigned")
        self.assertEqual(first_item["change"]["to"], f"{self.scene.worker.name} (Technician)")
        self.assertEqual(first_item["end_reason"], "REASSIGNED")
        self.assertIsNotNone(first_item["ended_at"])
        self.assertEqual(second_item["id"], f"assignment-{second.id}")
        self.assertEqual(second_item["change"]["from"], f"{self.scene.worker.name} (Technician)")
        self.assertEqual(second_item["worker"]["id"], second_worker.id)
        self.assertEqual(second_item["actor"]["id"], self.scene.poc.id)
        self.assertIsNone(second_item["ended_at"])
        self.assertEqual(len(body["department_changes"]), 1)
        change = body["department_changes"][0]
        self.assertEqual(change["id"], f"department-change-{forwarded.id}")
        self.assertEqual(change["note"], "Belongs to IT.")
        self.assertEqual(change["change"], {"field": "department", "from": "Technical", "to": "IT"})
        self.assertEqual(change["actor"]["id"], self.scene.poc.id)

    def test_a_ticket_with_no_history_returns_empty_lists(self) -> None:
        self.assertEqual(self.get_history().json(), {"assignments": [], "department_changes": []})

    def test_user_without_visibility_gets_404(self) -> None:
        self.assertEqual(self.get_history(create_scene().client_user).status_code, status.HTTP_404_NOT_FOUND)

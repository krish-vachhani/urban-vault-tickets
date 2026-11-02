"""The Django admin is the Phase 2 way to inspect seeded data, so its pages must load."""

import os
from io import StringIO
from unittest import mock

from django.contrib import admin
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User, UserRole

PROJECT_APP_LABELS = {"accounts", "organizations", "tickets", "notifications"}


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AdminPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        with mock.patch.dict(os.environ, {"SEED_DEMO_PASSWORD": "a-local-demo-password"}):
            call_command("seed_demo_data", stdout=StringIO())
        cls.admin_user = User.objects.create_superuser(
            email="admin@example.test", password="a-local-admin-password", name="Admin", role=UserRole.FACILITY_MANAGER
        )

    def setUp(self) -> None:
        self.client.force_login(self.admin_user)

    def project_admin_models(self):
        return [model for model in admin.site._registry if model._meta.app_label in PROJECT_APP_LABELS]

    def test_every_changelist_and_first_change_page_loads_with_seeded_data(self) -> None:
        for model in self.project_admin_models():
            url_name = f"admin:{model._meta.app_label}_{model._meta.model_name}"
            with self.subTest(model=model._meta.label):
                self.assertEqual(self.client.get(reverse(f"{url_name}_changelist")).status_code, 200)
                first_object = model.objects.first()
                # The seed writes no outbox rows, so that table has nothing to open.
                if first_object:
                    change_url = reverse(f"{url_name}_change", args=[first_object.pk])
                    self.assertEqual(self.client.get(change_url).status_code, 200)

    def test_ticket_search_by_issue_name_and_number_works(self) -> None:
        changelist_url = reverse("admin:tickets_ticket_changelist")

        self.assertEqual(self.client.get(changelist_url, {"q": "AC not cooling"}).status_code, 200)
        self.assertEqual(self.client.get(changelist_url, {"q": "1"}).status_code, 200)

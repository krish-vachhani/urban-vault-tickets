from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User, UserRole


class UserManagerTests(TestCase):
    def test_create_user_normalizes_email_and_hashes_password(self) -> None:
        user = User.objects.create_user(
            email="  Chaitanya.M@Example.COM ",
            password="a-strong-test-password",
            name="Chaitanya M",
            role=UserRole.CLIENT,
        )

        self.assertEqual(user.email, "chaitanya.m@example.com")
        self.assertNotEqual(user.password, "a-strong-test-password")
        self.assertTrue(user.check_password("a-strong-test-password"))
        self.assertFalse(user.is_staff)

    def test_create_superuser_grants_admin_access_but_keeps_business_role(self) -> None:
        admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="a-strong-test-password",
            name="Admin",
            role=UserRole.FACILITY_MANAGER,
        )

        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertEqual(admin_user.role, UserRole.FACILITY_MANAGER)


class UserConstraintTests(TestCase):
    def test_database_rejects_unknown_role(self) -> None:
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email="someone@example.com",
                password="a-strong-test-password",
                name="Someone",
                role="ADMIN",
            )

    def test_database_rejects_duplicate_email(self) -> None:
        User.objects.create_user(
            email="worker@example.com", password="pw-one-123456", name="Worker One", role=UserRole.WORKER
        )
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email="WORKER@example.com", password="pw-two-123456", name="Worker Two", role=UserRole.WORKER
            )

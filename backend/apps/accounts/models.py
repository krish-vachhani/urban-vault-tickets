"""The single custom User model shared by all four roles.

Department membership is intentionally NOT stored here: a Department POC is
linked through Department.poc_user and a Worker through DepartmentWorker
(both in the organizations app). See readmes/README-database-schema.md §2.1.
"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone


class UserRole(models.TextChoices):
    CLIENT = "CLIENT", "Client"
    FACILITY_MANAGER = "FACILITY_MANAGER", "Facility Manager"
    DEPARTMENT_POC = "DEPARTMENT_POC", "Department POC"
    WORKER = "WORKER", "Worker"


class UserManager(BaseUserManager):
    """Creates users that log in with their email address instead of a username."""

    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra_fields) -> "User":
        if not email:
            raise ValueError("Users must have an email address.")
        user = self.model(email=self.normalize_login_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields) -> "User":
        """Create a Django-admin user. It still needs one of the four business roles."""
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return self.create_user(email, password, **extra_fields)

    @staticmethod
    def normalize_login_email(email: str) -> str:
        """Store emails in lower case so login is case-insensitive."""
        return email.strip().lower()


class User(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=150)
    email = models.EmailField(max_length=255, unique=True)
    role = models.CharField(max_length=32, choices=UserRole.choices)
    is_active = models.BooleanField(default=True)
    # Controls access to the Django admin only; it is not a business role.
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["name", "role"]

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(role__in=UserRole.values),
                name="user_role_is_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_role_display()})"

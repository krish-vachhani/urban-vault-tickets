"""Clients, locations, Departments, Workers, and the Issue catalogue.

Schema reference: readmes/README-database-schema.md §2.2–§2.10.

Every foreign key uses on_delete=PROTECT. Tickets keep history, so a record
that a Ticket (or another mapping) refers to can never be deleted; retire it
with is_active=False instead.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.accounts.models import UserRole


class Client(models.Model):
    """An organization that uses a facility, such as Harness or Acme."""

    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, through="UserClient", related_name="clients")

    def __str__(self) -> str:
        return self.name


class UserClient(models.Model):
    """Maps a User of any role to a Client. What the mapping grants depends on the role."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="client_mappings")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="user_mappings")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "client"], name="userclient_unique_user_client"),
        ]

    def __str__(self) -> str:
        return f"{self.user.name} → {self.client.name}"


class Property(models.Model):
    """A building managed by Urban Vault, with exactly one designated Facility Manager."""

    name = models.CharField(max_length=255)
    # Optional: the schema leaves this open, and an address is not needed by any workflow rule.
    address = models.TextField(blank=True)
    facility_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="managed_properties",
        limit_choices_to={"role": UserRole.FACILITY_MANAGER},
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "properties"

    def __str__(self) -> str:
        return self.name


class ClientOffice(models.Model):
    """The part of a Property that one Client occupies. Tickets belong to an Office."""

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="offices")
    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name="client_offices")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    floors = models.ManyToManyField("Floor", through="ClientOfficeFloor", related_name="client_offices")

    class Meta:
        constraints = [
            # A blank code means "no code", so only real codes must be unique within a Client.
            models.UniqueConstraint(
                fields=["client", "code"],
                condition=~Q(code=""),
                name="clientoffice_unique_client_code",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Floor(models.Model):
    """A physical floor of a Property."""

    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name="floors")
    name = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["property", "name"], name="floor_unique_property_name"),
        ]

    def __str__(self) -> str:
        return f"{self.property.name} – {self.name}"


class ClientOfficeFloor(models.Model):
    """Records that a Client Office occupies a Floor. Several Offices may share a Floor."""

    client_office = models.ForeignKey(ClientOffice, on_delete=models.PROTECT, related_name="floor_mappings")
    floor = models.ForeignKey(Floor, on_delete=models.PROTECT, related_name="office_mappings")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["client_office", "floor"], name="officefloor_unique_office_floor"),
        ]

    def clean(self) -> None:
        if self.client_office_id and self.floor_id and self.client_office.property_id != self.floor.property_id:
            raise ValidationError("The Floor must belong to the same Property as the Client Office.")

    def __str__(self) -> str:
        return f"{self.client_office.name} → {self.floor.name}"


class Department(models.Model):
    """An organization-wide Department with exactly one designated POC."""

    name = models.CharField(max_length=100, unique=True)
    # One-to-one: a POC can lead only one Department. User has no department field.
    poc_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="poc_department",
        limit_choices_to={"role": UserRole.DEPARTMENT_POC},
    )
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class DepartmentWorker(models.Model):
    """Puts a Worker in a Department. The unique worker keeps a Worker in at most one."""

    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="worker_memberships")
    worker = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="department_membership",
        limit_choices_to={"role": UserRole.WORKER},
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.worker.name} → {self.department.name}"


class Issue(models.Model):
    """A selectable issue type, such as "AC not cooling". Belongs to exactly one Department."""

    name = models.CharField(max_length=255)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="issues")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["department", "name"], name="issue_unique_department_name"),
        ]

    def __str__(self) -> str:
        return self.name

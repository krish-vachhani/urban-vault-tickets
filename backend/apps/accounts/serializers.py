from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from apps.accounts.models import User, UserRole
from apps.organizations.role_labels import get_role_label


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class CurrentUserSerializer(serializers.ModelSerializer):
    """The authenticated user's own profile (readmes/README-authentication.md §6.5).

    Department and Client data are read through the reverse relations created by the
    organizations app, because accounts must not import organizations models.
    """

    role_label = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    clients = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "email", "role", "role_label", "department", "clients"]

    def get_role_label(self, user: User) -> str:
        return get_role_label(user)

    def get_department(self, user: User) -> dict | None:
        department = self._find_department(user)
        if department is None:
            return None
        return {"id": department.id, "name": department.name}

    def get_clients(self, user: User) -> list[dict]:
        active_clients = user.clients.filter(is_active=True).order_by("name")
        return [{"id": client.id, "name": client.name} for client in active_clients]

    @staticmethod
    def _find_department(user: User):
        """A POC leads a Department; a Worker belongs to one; other roles have none."""
        try:
            if user.role == UserRole.DEPARTMENT_POC:
                return user.poc_department
            if user.role == UserRole.WORKER:
                return user.department_membership.department
        except ObjectDoesNotExist:
            return None
        return None

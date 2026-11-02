from rest_framework import serializers

from apps.organizations.models import ClientOffice, Issue


class IdNameSerializer(serializers.Serializer):
    """The {id, name} shape shared by Clients, Floors, Departments and Workers."""

    id = serializers.IntegerField()
    name = serializers.CharField()


class ClientOfficeSerializer(serializers.ModelSerializer):
    property = IdNameSerializer()
    floor_count = serializers.IntegerField()

    class Meta:
        model = ClientOffice
        fields = ["id", "name", "code", "property", "floor_count"]


class IssueSerializer(serializers.ModelSerializer):
    department = IdNameSerializer()

    class Meta:
        model = Issue
        fields = ["id", "name", "department"]


class QuickIssueSerializer(serializers.ModelSerializer):
    department_id = serializers.IntegerField()
    occurrences = serializers.IntegerField()
    last_reported_at = serializers.DateTimeField()

    class Meta:
        model = Issue
        fields = ["id", "name", "department_id", "occurrences", "last_reported_at"]

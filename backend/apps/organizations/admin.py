"""Django admin for inspecting organization data. Not part of the product UI."""

from django.contrib import admin

from apps.organizations.models import (
    Client,
    ClientOffice,
    ClientOfficeFloor,
    Department,
    DepartmentWorker,
    Floor,
    Issue,
    Property,
    UserClient,
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]


@admin.register(UserClient)
class UserClientAdmin(admin.ModelAdmin):
    list_display = ["user", "client", "created_at"]
    list_filter = ["client", "user__role"]
    search_fields = ["user__name", "user__email", "client__name"]
    list_select_related = ["user", "client"]


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ["name", "facility_manager", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "address"]
    list_select_related = ["facility_manager"]


@admin.register(ClientOffice)
class ClientOfficeAdmin(admin.ModelAdmin):
    list_display = ["name", "client", "property", "code", "is_active"]
    list_filter = ["client", "property", "is_active"]
    search_fields = ["name", "code"]
    list_select_related = ["client", "property"]


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ["name", "property"]
    list_filter = ["property"]
    list_select_related = ["property"]


@admin.register(ClientOfficeFloor)
class ClientOfficeFloorAdmin(admin.ModelAdmin):
    list_display = ["client_office", "floor"]
    list_filter = ["client_office__property"]
    list_select_related = ["client_office", "floor__property"]


class IssueInline(admin.TabularInline):
    model = Issue
    extra = 0


class DepartmentWorkerInline(admin.TabularInline):
    model = DepartmentWorker
    extra = 0


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "poc_user", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    list_select_related = ["poc_user"]
    inlines = [DepartmentWorkerInline, IssueInline]


@admin.register(DepartmentWorker)
class DepartmentWorkerAdmin(admin.ModelAdmin):
    list_display = ["worker", "department", "created_at"]
    list_filter = ["department"]
    search_fields = ["worker__name", "worker__email"]
    list_select_related = ["worker", "department"]


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ["name", "department", "is_active"]
    list_filter = ["department", "is_active"]
    search_fields = ["name"]
    list_select_related = ["department"]

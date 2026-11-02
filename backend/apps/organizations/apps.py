from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    """Clients, Properties, Offices, Floors, Departments, Workers, and the Issue catalogue."""

    name = "apps.organizations"
    # Short label keeps model references stable, e.g. "organizations.ModelName".
    label = "organizations"
    verbose_name = "Organizations"

"""Root URL configuration. All REST endpoints live under /api/v1/."""

from django.contrib import admin
from django.urls import include, path

from config.health import HealthCheckView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.organizations.urls")),
    path("api/v1/", include("apps.tickets.urls")),
    path("api/v1/health/", HealthCheckView.as_view(), name="health-check"),
]

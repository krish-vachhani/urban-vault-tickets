"""Root URL configuration. All REST endpoints live under /api/v1/."""

from django.contrib import admin
from django.urls import path

from config.health import HealthCheckView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", HealthCheckView.as_view(), name="health-check"),
]

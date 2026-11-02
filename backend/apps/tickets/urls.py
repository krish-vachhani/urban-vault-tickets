from django.urls import path

from apps.tickets import views

# The ID is matched as a plain string so a malformed one returns 400, not a bare routing 404.
urlpatterns = [
    path("tickets/<str:ticket_id>/eligible-workers/", views.EligibleWorkersView.as_view(), name="ticket-eligible-workers"),
]

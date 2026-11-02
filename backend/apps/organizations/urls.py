from django.urls import path

from apps.organizations import views

# IDs are matched as plain strings so a malformed one returns 400, not a bare routing 404.
urlpatterns = [
    path("me/clients/", views.MyClientsView.as_view(), name="my-clients"),
    path("clients/<str:client_id>/offices/", views.ClientOfficesView.as_view(), name="client-offices"),
    path("clients/<str:client_id>/quick-issues/", views.ClientQuickIssuesView.as_view(), name="client-quick-issues"),
    path("client-offices/<str:client_office_id>/floors/", views.OfficeFloorsView.as_view(), name="office-floors"),
    path("departments/", views.DepartmentsView.as_view(), name="departments"),
    path("issues/", views.IssuesView.as_view(), name="issues"),
]

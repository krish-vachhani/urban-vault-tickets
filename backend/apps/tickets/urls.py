from rest_framework.routers import SimpleRouter

from apps.tickets import views

router = SimpleRouter()
router.register("tickets", views.TicketViewSet, basename="ticket")

urlpatterns = router.urls

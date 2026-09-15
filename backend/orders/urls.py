from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import OrderViewSet, StaffStatsView

router = DefaultRouter()
router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("staff/stats/", StaffStatsView.as_view()),
    *router.urls,
]

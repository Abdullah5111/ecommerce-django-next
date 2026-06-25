from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import NotificationViewSet, PushConfigView, PushSubscribeView

router = DefaultRouter()
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("push/config/", PushConfigView.as_view(), name="push-config"),
    path("push/subscribe/", PushSubscribeView.as_view(), name="push-subscribe"),
    *router.urls,
]

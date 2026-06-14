from rest_framework.routers import DefaultRouter

from .views import ReturnViewSet

router = DefaultRouter()
router.register("returns", ReturnViewSet, basename="return")

urlpatterns = router.urls

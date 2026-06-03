from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView

from .views import RegisterView, MeView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
    path("logout/", TokenBlacklistView.as_view(), name="logout"),
]

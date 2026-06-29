from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenBlacklistView

from .views import (
    AddressViewSet,
    AvatarView,
    ForgotPasswordView,
    GoogleConfigView,
    GoogleLoginView,
    MeView,
    PhoneSendCodeView,
    PhoneVerifyView,
    RegisterView,
    ResetPasswordView,
    VerifyEmailView,
)

router = DefaultRouter()
router.register(r"addresses", AddressViewSet, basename="address")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
    path("me/avatar/", AvatarView.as_view(), name="avatar"),
    path("logout/", TokenBlacklistView.as_view(), name="logout"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify_email"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset_password"),
    path("phone/send-code/", PhoneSendCodeView.as_view(), name="phone_send_code"),
    path("phone/verify/", PhoneVerifyView.as_view(), name="phone_verify"),
    path("google/config/", GoogleConfigView.as_view(), name="google_config"),
    path("google/", GoogleLoginView.as_view(), name="google_login"),
    path("", include(router.urls)),
]

import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Address
from .serializers import (
    AddressSerializer,
    EmailOrUsernameTokenObtainPairSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        link = f"{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"
        send_mail(
            "Verify your email",
            f"Click to verify: {link}",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class AvatarView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    MAX_BYTES = 2 * 1024 * 1024  # 2 MB

    def post(self, request):
        upload = request.FILES.get("avatar")
        if upload is None:
            return Response(
                {"detail": "No image provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if upload.size > self.MAX_BYTES:
            return Response(
                {"detail": "Image must be 2 MB or smaller."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from PIL import Image

            Image.open(upload).verify()
            upload.seek(0)
        except Exception:
            return Response(
                {"detail": "Invalid image file."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        user.avatar.delete(save=False)  # drop the previous file, if any
        user.avatar = upload
        user.save(update_fields=["avatar"])
        return Response(UserSerializer(user, context={"request": request}).data)

    def delete(self, request):
        user = request.user
        if user.avatar:
            user.avatar.delete(save=False)
            user.avatar = None
            user.save(update_fields=["avatar"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailOrUsernameTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailOrUsernameTokenObtainPairSerializer


def _get_user_from_uid(uid):
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        return User.objects.get(pk=pk)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uid = request.data.get("uid", "")
        token = request.data.get("token", "")
        user = _get_user_from_uid(uid)
        if user is None or not default_token_generator.check_token(user, token):
            return Response(
                {"detail": "Invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        return Response({"detail": "Email verified"})


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email", "")
        generic_response = Response(
            {"detail": "If that email exists, a reset link was sent."}
        )
        if not email:
            return generic_response
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return generic_response
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
        send_mail(
            "Reset your password",
            f"Click to reset your password: {link}",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
        return generic_response


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uid = request.data.get("uid", "")
        token = request.data.get("token", "")
        new_password = request.data.get("new_password", "")
        user = _get_user_from_uid(uid)
        if user is None or not default_token_generator.check_token(user, token):
            return Response(
                {"detail": "Invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return Response(
                {"detail": list(e.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new_password)
        user.save()
        return Response({"detail": "Password reset"})


OTP_TTL = 600  # code is valid for 10 minutes
OTP_COOLDOWN = 30  # seconds a user must wait between sends


def _otp_key(user_id):
    return f"phone_otp:{user_id}"


def _otp_cooldown_key(user_id):
    return f"phone_otp_cooldown:{user_id}"


class PhoneSendCodeView(APIView):
    """Generate a one-time code for a phone number and 'send' it.

    Mirrors the email-verification flow: in dev the code is written to the
    server console (swap for a real SMS provider in production).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        phone = (request.data.get("phone") or "").strip()
        if not phone:
            return Response(
                {"detail": "Phone number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        if cache.get(_otp_cooldown_key(user.id)):
            return Response(
                {"detail": "Please wait before requesting another code."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        code = f"{secrets.randbelow(1_000_000):06d}"
        cache.set(_otp_key(user.id), {"code": code, "phone": phone}, OTP_TTL)
        cache.set(_otp_cooldown_key(user.id), True, OTP_COOLDOWN)
        print(f"[DEV] SMS to {phone}: your verification code is {code}")
        return Response({"detail": "Verification code sent."})


class PhoneVerifyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = (request.data.get("code") or "").strip()
        user = request.user
        data = cache.get(_otp_key(user.id))
        if not data or code != data["code"]:
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.phone = data["phone"]
        user.phone_verified = True
        user.save(update_fields=["phone", "phone_verified"])
        cache.delete(_otp_key(user.id))
        cache.delete(_otp_cooldown_key(user.id))
        return Response(UserSerializer(user, context={"request": request}).data)


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        address = self.get_object()
        address.is_default_shipping = True
        address.save()
        return Response(AddressSerializer(address).data)

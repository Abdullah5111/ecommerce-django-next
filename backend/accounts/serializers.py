from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Address

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "address",
            "phone",
            "email_verified",
            "phone_verified",
            "avatar",
            "display_name",
            "bio",
            "date_of_birth",
            "gender",
        )
        read_only_fields = (
            "id",
            "email",
            "email_verified",
            "phone",
            "phone_verified",
            "avatar",
        )

    def get_avatar(self, obj):
        if not obj.avatar:
            return None
        url = obj.avatar.url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        identifier = attrs.get(self.username_field, "")
        if identifier and "@" in identifier:
            try:
                user = User.objects.get(email__iexact=identifier)
                attrs[self.username_field] = user.get_username()
            except User.DoesNotExist:
                pass
        return super().validate(attrs)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("username", "email", "password", "first_name", "last_name")

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "id",
            "label",
            "recipient",
            "phone",
            "line1",
            "line2",
            "city",
            "state",
            "postal_code",
            "country",
            "is_default_shipping",
            "is_default_billing",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

"""OpenAPI (drf-spectacular) extensions and shared shapes for accounts.

drf-spectacular matches authenticator extensions on the exact class, so its
built-in SimpleJWT scheme doesn't cover our RevocableJWTAuthentication
subclass. Without this the schema has no security scheme and Swagger's
"Authorize" button disappears. Imported in AccountsConfig.ready().

The plain APIViews here take and return small ad-hoc bodies; the shapes
below describe them so the docs show real fields instead of "no body".
"""
from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme
from drf_spectacular.utils import OpenApiResponse, inline_serializer
from rest_framework import serializers


class RevocableJWTScheme(SimpleJWTScheme):
    target_class = "accounts.authentication.RevocableJWTAuthentication"


def body(name, **fields):
    """A named, documented request/response shape."""
    return inline_serializer(name=name, fields=fields)


DETAIL = body("Detail", detail=serializers.CharField())
# Sign-in style responses: the refresh token is set as an httpOnly cookie.
ACCESS = body("AccessToken", access=serializers.CharField())
ERROR = OpenApiResponse(DETAIL, description="Explained in `detail`.")

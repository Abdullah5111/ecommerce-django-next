"""OpenAPI (drf-spectacular) extensions for accounts.

drf-spectacular matches authenticator extensions on the exact class, so its
built-in SimpleJWT scheme doesn't cover our RevocableJWTAuthentication
subclass. Without this the schema has no security scheme and Swagger's
"Authorize" button disappears. Imported in AccountsConfig.ready().
"""
from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class RevocableJWTScheme(SimpleJWTScheme):
    target_class = "accounts.authentication.RevocableJWTAuthentication"

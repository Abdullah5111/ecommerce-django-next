"""Storage for phone verification codes — fails closed when Redis is down.

Codes, their attempt counts and the resend cooldown live on the ``otp`` cache
alias: the same Redis (and keys) as the default cache, but kept separate so
that making the default cache tolerate outages can never make phone
verification "succeed" without a stored code. Any Redis error on this path,
including the endpoints' own rate limiter, becomes a 503.
"""
from django.core.cache import caches
from django.utils.connection import ConnectionProxy
from redis.exceptions import RedisError
from rest_framework.exceptions import APIException
from rest_framework.throttling import ScopedRateThrottle

otp_cache = ConnectionProxy(caches, "otp")


class OtpStoreUnavailable(APIException):
    status_code = 503
    default_detail = "Phone verification is temporarily unavailable. Try again shortly."
    default_code = "otp_store_unavailable"


class PhoneRateThrottle(ScopedRateThrottle):
    """``ScopedRateThrottle`` on the strict ``otp`` cache: when the counters
    can't be read the request is refused (503), not waved through or 500'd."""

    cache = otp_cache

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except RedisError as exc:
            raise OtpStoreUnavailable() from exc

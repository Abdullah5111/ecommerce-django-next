from rest_framework.permissions import SAFE_METHODS
from rest_framework.throttling import UserRateThrottle


class WriteOnlyUserRateThrottle(UserRateThrottle):
    """Throttles writes while leaving reads alone — the reviews route serves a
    public GET and an authed POST, and browsing must not be rate-limited.
    """

    def allow_request(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return super().allow_request(request, view)


class ReviewWriteThrottle(WriteOnlyUserRateThrottle):
    """Posting a review — the expensive one: up to 5 file uploads per call."""

    scope = "review-write"


class ReviewVoteThrottle(WriteOnlyUserRateThrottle):
    """Toggling a helpful vote — cheap per call, but trivially spammable."""

    scope = "review-vote"

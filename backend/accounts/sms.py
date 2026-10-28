"""Outbound SMS for phone verification codes.

``SMS_BACKEND`` picks the provider:

- ``"twilio"`` — Twilio's Messages API (``TWILIO_ACCOUNT_SID``,
  ``TWILIO_AUTH_TOKEN``, and ``TWILIO_FROM_NUMBER`` or
  ``TWILIO_MESSAGING_SERVICE_SID``). Plain HTTPS via urllib; no SDK.
- ``"console"`` — prints the message. Dev and tests only: it puts the code in
  the process output.
- ``""`` — not configured; ``send_sms`` raises ``SmsUnavailable``.

Defaults to ``"console"`` under DEBUG and to unconfigured otherwise, so a
production deploy without a provider refuses to send instead of pretending.
"""
import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
TIMEOUT_SECONDS = 10


class SmsUnavailable(Exception):
    """No SMS provider is configured."""


class SmsSendError(Exception):
    """The provider refused or could not be reached."""


def is_configured() -> bool:
    return bool(getattr(settings, "SMS_BACKEND", ""))


def send_sms(to: str, body: str) -> None:
    backend = getattr(settings, "SMS_BACKEND", "")
    if backend == "console":
        print(f"[SMS to {to}] {body}")
    elif backend == "twilio":
        _send_twilio(to, body)
    elif not backend:
        raise SmsUnavailable("SMS is not configured.")
    else:
        raise SmsUnavailable(f"Unknown SMS_BACKEND {backend!r}.")


def _send_twilio(to: str, body: str) -> None:
    sid = settings.TWILIO_ACCOUNT_SID
    token = settings.TWILIO_AUTH_TOKEN
    if not (sid and token):
        raise SmsUnavailable("Twilio credentials are not set.")
    fields = {"To": to, "Body": body}
    if settings.TWILIO_MESSAGING_SERVICE_SID:
        fields["MessagingServiceSid"] = settings.TWILIO_MESSAGING_SERVICE_SID
    elif settings.TWILIO_FROM_NUMBER:
        fields["From"] = settings.TWILIO_FROM_NUMBER
    else:
        raise SmsUnavailable("Set TWILIO_FROM_NUMBER or TWILIO_MESSAGING_SERVICE_SID.")

    credentials = base64.b64encode(f"{sid}:{token}".encode()).decode()
    request = urllib.request.Request(
        TWILIO_API.format(sid=urllib.parse.quote(sid)),
        data=urllib.parse.urlencode(fields).encode(),
        headers={"Authorization": f"Basic {credentials}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            sid_sent = json.loads(response.read() or b"{}").get("sid", "")
    except urllib.error.HTTPError as exc:
        # Twilio's error body names the problem (bad number, unverified trial
        # recipient, …); log it, but never the message body — it holds the code.
        detail = exc.read()[:500].decode("utf-8", "replace")
        logger.warning("Twilio rejected SMS (%s): %s", exc.code, detail)
        raise SmsSendError(f"SMS provider returned {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("Twilio unreachable: %s", exc)
        raise SmsSendError("SMS provider unreachable.") from exc
    logger.info("SMS sent via Twilio (%s)", sid_sent)

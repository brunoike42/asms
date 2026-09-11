"""
Twilio SMS provider — the fallback in the default chain.

Twilio's own error codes distinguish permanent from transient failures
clearly (e.g. 21211 "invalid To phone number" is permanent; 20429 "too many
requests" and 5xx transport errors are transient) — see
https://www.twilio.com/docs/api/errors. We use that same distinction here so
the circuit breaker only trips on failures that are actually the provider's
fault, not on malformed input.
"""
from ..exceptions import ProviderSendError
from .base import BaseSMSProvider, SMSProviderResult

# Twilio error codes that mean "this input is bad" — retrying anywhere won't help.
_PERMANENT_ERROR_CODES = {
    21211,  # Invalid 'To' Phone Number
    21610,  # Recipient has opted out (unsubscribed)
    21614,  # 'To' number is not a valid mobile number
    21408,  # Permission to send an SMS has not been enabled for the region
}


class TwilioProvider(BaseSMSProvider):
    name = "twilio"

    def __init__(self, account_sid, auth_token, from_number):
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = from_number
        self._client = None

    def _get_client(self):
        if self._client is None:
            from twilio.rest import Client

            self._client = Client(self._account_sid, self._auth_token)
        return self._client

    def send(self, phone_e164, message, sender_id=None):
        client = self._get_client()
        from_number = sender_id or self._from_number

        try:
            msg = client.messages.create(to=phone_e164, from_=from_number, body=message)
        except Exception as exc:
            code = getattr(exc, "code", None)
            is_transient = code not in _PERMANENT_ERROR_CODES if code is not None else True
            raise ProviderSendError(
                f"Twilio send failed (code={code}): {exc}",
                is_transient=is_transient,
                provider=self.name,
            ) from exc

        if msg.error_code:
            is_transient = msg.error_code not in _PERMANENT_ERROR_CODES
            raise ProviderSendError(
                f"Twilio reported error_code={msg.error_code}: {msg.error_message}",
                is_transient=is_transient,
                provider=self.name,
                raw_response={"sid": msg.sid, "error_code": msg.error_code},
            )

        return SMSProviderResult(
            provider=self.name,
            message_id=msg.sid,
            status=msg.status,
            cost=str(msg.price) if msg.price else None,
            raw_response={"sid": msg.sid, "status": msg.status},
        )

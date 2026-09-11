"""
Africa's Talking SMS provider.

Uses the official africastalking Python SDK. Import is deferred into
__init__ so this module can be imported (e.g. for tests) even in
environments where the SDK isn't installed and this provider isn't
configured.

Status codes: Africa's Talking returns a statusCode per recipient in the
response (101 = Success/Sent). We treat a small set of clearly-permanent
rejection reasons as non-transient (don't bother failing over — a different
provider is very unlikely to fix a garbage number), and everything else as
transient (network blips, telco congestion, temporary account issues) so the
service layer will try the next provider in the chain.

See https://developers.africastalking.com/docs/sms/sending/bulk for the
authoritative status code table — the strings below are matched
case-insensitively against the provider's status message since AT's SDK
surfaces the human-readable string more reliably across SDK versions than a
numeric code.
"""
from ..exceptions import ProviderSendError
from .base import BaseSMSProvider, SMSProviderResult

_PERMANENT_FAILURE_MARKERS = (
    "invalid phone number",
    "invalid sender id",
    "blacklisted",
    "user in blacklist",
    "unsupported number type",
)


class AfricasTalkingProvider(BaseSMSProvider):
    name = "africastalking"

    def __init__(self, username, api_key, sender_id=None, sandbox=False):
        self._username = username
        self._api_key = api_key
        self._default_sender_id = sender_id
        self._sandbox = sandbox
        self._sms = None  # lazily initialized SDK client

    def _client(self):
        if self._sms is None:
            import africastalking

            africastalking.initialize(self._username, self._api_key)
            self._sms = africastalking.SMS
        return self._sms

    def send(self, phone_e164, message, sender_id=None):
        sms = self._client()
        effective_sender = sender_id or self._default_sender_id

        try:
            if effective_sender:
                response = sms.send(message, [phone_e164], effective_sender)
            else:
                response = sms.send(message, [phone_e164])
        except Exception as exc:  # SDK network/transport errors: always transient
            raise ProviderSendError(
                f"Africa's Talking transport error: {exc}",
                is_transient=True,
                provider=self.name,
            ) from exc

        recipients = response.get("SMSMessageData", {}).get("Recipients", [])
        if not recipients:
            raise ProviderSendError(
                f"Africa's Talking returned no recipients in response: {response}",
                is_transient=True,
                provider=self.name,
                raw_response=response,
            )

        recipient = recipients[0]
        status = str(recipient.get("status", "")).strip()

        if status.lower() != "success":
            lowered = status.lower()
            is_transient = not any(marker in lowered for marker in _PERMANENT_FAILURE_MARKERS)
            raise ProviderSendError(
                f"Africa's Talking rejected message: {status}",
                is_transient=is_transient,
                provider=self.name,
                raw_response=response,
            )

        return SMSProviderResult(
            provider=self.name,
            message_id=recipient.get("messageId", ""),
            status=status,
            cost=recipient.get("cost"),
            raw_response=response,
        )

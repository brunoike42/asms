"""
Console provider — logs the message instead of sending it. Wire this in for
local development and CI so engineers don't accidentally SMS a real parent
while testing, and so tests don't need network access or credentials.
"""
import logging
import uuid

from .base import BaseSMSProvider, SMSProviderResult

logger = logging.getLogger("notifications.sms.console")


class ConsoleProvider(BaseSMSProvider):
    name = "console"

    def send(self, phone_e164, message, sender_id=None):
        message_id = f"console-{uuid.uuid4().hex[:12]}"
        logger.info("SMS (console) -> %s: %s [id=%s]", phone_e164, message, message_id)
        return SMSProviderResult(
            provider=self.name,
            message_id=message_id,
            status="Success",
            cost="0.0000",
        )

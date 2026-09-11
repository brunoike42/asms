"""
Provider interface. Every concrete provider (Africa's Talking, Twilio,
console/dev) implements this same shape so the SMSService can treat them
interchangeably and fail over between them without caring which one it's
talking to.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SMSProviderResult:
    provider: str
    message_id: str
    status: str  # provider's own status string, e.g. "Success", "queued"
    cost: Optional[str] = None
    raw_response: Optional[dict] = None


class BaseSMSProvider(ABC):
    #: Short, stable name used in logs, circuit breaker keys, and the
    #: SMSMessage.provider column. Never change this once in production —
    #: it'd orphan the breaker's failure history and historical records.
    name: str = "base"

    @abstractmethod
    def send(self, phone_e164: str, message: str, sender_id: Optional[str] = None) -> SMSProviderResult:
        """Send one SMS. Must raise ProviderSendError on failure, with
        is_transient set correctly — this is what the service layer uses to
        decide whether to fail over to the next provider or give up."""
        raise NotImplementedError

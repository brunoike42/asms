"""
SMSMessage — the durable record of every send attempt.

Why this exists even though SMSService already returns a SendOutcome: the
in-memory outcome disappears the moment the Celery task finishes. Without a
DB row you can't answer "did this parent actually get notified", can't
reconcile delivery receipts arriving later via webhook, and can't debug why
a tenant's messages are failing.

TENANT MODEL: this project already has a shared TenantModel abstract base
(apps/core/models.py) that every concrete model inherits — it provides
tenant, created_at, and updated_at automatically. SMSMessage follows the
same convention as Vehicle/Driver/etc. rather than inventing a separate
settings-based tenant reference.
"""
from django.db import models

from apps.core.models import TenantManager, TenantModel


class SMSMessage(TenantModel):
    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        RATE_LIMITED = "rate_limited", "Rate limited"
        INVALID_NUMBER = "invalid_number", "Invalid number"
        DUPLICATE_SUPPRESSED = "duplicate_suppressed", "Duplicate suppressed"

    # tenant, created_at, updated_at all come from TenantModel.
    phone_e164 = models.CharField(max_length=20, db_index=True)
    message = models.TextField()
    status = models.CharField(max_length=24, choices=Status.choices, db_index=True)

    provider = models.CharField(max_length=32, blank=True)
    provider_message_id = models.CharField(max_length=128, blank=True, db_index=True)
    cost = models.CharField(max_length=32, blank=True)
    error_message = models.TextField(blank=True)

    idempotency_key = models.CharField(max_length=64, blank=True, db_index=True)
    attempt_log = models.JSONField(default=list, blank=True)

    delivered_at = models.DateTimeField(null=True, blank=True)

    # Matches project convention: auto-scopes queries to the current
    # request's tenant when one is set (see apps/core/models.py). Falls
    # back to unfiltered when there's no tenant in context — e.g. inside a
    # Celery task or a provider webhook — same behavior every other
    # TenantModel subclass already has.
    objects = TenantManager()

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["provider", "status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"SMSMessage(id={self.pk}, phone={self.phone_e164}, status={self.status})"

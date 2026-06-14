from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

from apps.core.models import TenantModel


def generate_merchant_ref():
    """Short unique merchant reference — max 50 chars for PesaPal."""
    return f'ASMS-{uuid.uuid4().hex[:12].upper()}'


class PesaPalTransaction(TenantModel):
    """
    One record per payment attempt against a FeeInvoice.
    A single invoice may have multiple transaction attempts
    (e.g. parent abandons first attempt, retries).
    Only one should reach COMPLETED.
    """

    STATUS_PENDING   = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED    = 'failed'
    STATUS_REVERSED  = 'reversed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED   = 'expired'

    STATUS_CHOICES = [
        (STATUS_PENDING,   'Pending — Awaiting parent action'),
        (STATUS_COMPLETED, 'Completed — Payment confirmed'),
        (STATUS_FAILED,    'Failed'),
        (STATUS_REVERSED,  'Reversed / Refunded'),
        (STATUS_CANCELLED, 'Cancelled by parent'),
        (STATUS_EXPIRED,   'Expired — No action taken'),
    ]

    CURRENCY_CHOICES = [
        ('UGX', 'Ugandan Shilling'),
        ('KES', 'Kenyan Shilling'),
        ('TZS', 'Tanzanian Shilling'),
        ('USD', 'US Dollar'),
    ]

    # ── Core links ────────────────────────────────
    invoice = models.ForeignKey(
        'finance.FeeInvoice',
        on_delete=models.PROTECT,
        related_name='pesapal_transactions',
    )
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.PROTECT,
        related_name='pesapal_transactions',
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='initiated_payments',
        help_text='Staff or parent who started this transaction',
    )

    # ── Our reference ──────────────────────────────
    merchant_reference = models.CharField(
        max_length=50, unique=True,
        default=generate_merchant_ref,
        help_text='Our unique reference sent to PesaPal',
    )

    # ── PesaPal references (filled after order submission) ──
    order_tracking_id = models.CharField(
        max_length=100, blank=True,
        help_text='PesaPal order tracking ID returned on submission',
    )
    redirect_url = models.URLField(
        max_length=500, blank=True,
        help_text='PesaPal redirect URL where parent completes payment',
    )

    # ── Amount ────────────────────────────────────
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='UGX')

    # ── Payer details (parent) ────────────────────
    payer_first_name = models.CharField(max_length=100, blank=True)
    payer_last_name  = models.CharField(max_length=100, blank=True)
    payer_phone      = models.CharField(
        max_length=20, blank=True,
        help_text='Phone number for MTN/Airtel USSD STK push',
    )
    payer_email      = models.CharField(max_length=200, blank=True)

    # ── Status ────────────────────────────────────
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
        db_index=True,
    )
    payment_method = models.CharField(
        max_length=50, blank=True,
        help_text='e.g. MTN Mobile Money, Airtel Money, Visa, Mastercard',
    )
    payment_account = models.CharField(
        max_length=100, blank=True,
        help_text='Masked phone or card number returned by PesaPal',
    )

    # ── PesaPal confirmation (filled on IPN) ──────
    confirmation_code = models.CharField(
        max_length=100, blank=True,
        help_text='PesaPal confirmation / receipt code',
    )
    pesapal_status_code    = models.IntegerField(null=True, blank=True)
    pesapal_status_message = models.CharField(max_length=100, blank=True)

    # ── Finance link (filled after invoice updated) ──
    finance_payment = models.OneToOneField(
        'finance.Payment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pesapal_transaction',
        help_text='The Payment record created in finance module on confirmation',
    )

    # ── Raw responses ─────────────────────────────
    submit_response  = models.JSONField(default=dict, blank=True)
    status_response  = models.JSONField(default=dict, blank=True)

    # ── Timestamps ────────────────────────────────
    initiated_at  = models.DateTimeField(auto_now_add=True)
    completed_at  = models.DateTimeField(null=True, blank=True)
    expires_at    = models.DateTimeField(
        null=True, blank=True,
        help_text='Transaction expires if no action taken (default: 30 min)',
    )

    class Meta:
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['order_tracking_id']),
            models.Index(fields=['merchant_reference']),
            models.Index(fields=['status']),
            models.Index(fields=['invoice']),
        ]

    def __str__(self):
        return f'{self.merchant_reference} — {self.amount} {self.currency} — {self.status}'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=30)
        super().save(*args, **kwargs)

    @property
    def is_complete(self):
        return self.status == self.STATUS_COMPLETED

    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING

    @property
    def payer_full_name(self):
        return f'{self.payer_first_name} {self.payer_last_name}'.strip()

    def get_status_badge_class(self):
        return {
            self.STATUS_PENDING:   'bg-warning text-dark',
            self.STATUS_COMPLETED: 'bg-success',
            self.STATUS_FAILED:    'bg-danger',
            self.STATUS_REVERSED:  'bg-secondary',
            self.STATUS_CANCELLED: 'bg-secondary',
            self.STATUS_EXPIRED:   'bg-dark',
        }.get(self.status, 'bg-secondary')


class IPNLog(models.Model):
    """
    Raw log of every IPN notification received from PesaPal.
    We store first, process second — ensures we never lose a payment signal.
    """

    order_tracking_id        = models.CharField(max_length=100, db_index=True)
    order_merchant_reference = models.CharField(max_length=100, blank=True)
    notification_type        = models.CharField(max_length=50, blank=True)
    raw_query_string         = models.TextField(
        blank=True, help_text='Full raw query string from PesaPal IPN GET request'
    )

    processed    = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_log    = models.TextField(blank=True)

    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        status = 'processed' if self.processed else 'pending'
        return f'IPN {self.order_tracking_id} [{status}] @ {self.received_at:%d %b %H:%M}'

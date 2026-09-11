"""
ASMS Platform Billing — Phase 5A (data layer only)

This is ASMS Ltd charging SCHOOLS to use the platform. It is deliberately
separate from apps.finance, which is schools charging THEIR OWN parents —
Section 5 of the spec is explicit that these must never be conflated.

Plan is not tenant-scoped: it's ASMS Ltd's own pricing catalogue, the same
across every tenant. PlatformInvoice snapshots `amount` at issue time so a
future price change never rewrites a historical invoice.

Gateway wiring (PesaPal recurring charges, MoMo/Airtel renewal prompts,
IPN handling) is Phase 5C — not here. PlatformPayment.method already has
the rails Phase 5C will need so this model doesn't move again.
"""
import uuid
from django.db import models
from django.utils import timezone
from apps.core.models import TenantModel


class Plan(models.Model):
    """
    Pricing/limits config for each Tenant.PlanChoices value.
    Kept separate from Tenant so pricing can change without a migration
    touching every tenant row, and so historical invoices can reference
    the plan without inheriting live price changes.
    """
    class BillingIntervalChoices(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        ANNUAL  = 'annual',  'Annual'
        CUSTOM  = 'custom',  'Custom / By Engagement'

    slug = models.CharField(
        max_length=20, unique=True,
        help_text='Must match a Tenant.PlanChoices value exactly (trial/starter/growth/...)'
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)

    base_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    included_students = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Students covered by base_price before price_per_extra_student kicks in'
    )
    max_students = models.PositiveIntegerField(
        null=True, blank=True, help_text='Plan ceiling. Null = no cap (Network/Government).'
    )
    price_per_extra_student = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    max_users = models.PositiveIntegerField(null=True, blank=True, help_text='Null = unlimited')
    storage_gb = models.PositiveIntegerField(default=5)
    sms_bundle = models.PositiveIntegerField(default=0, help_text='SMS units included per period')
    sms_overage_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    billing_interval = models.CharField(
        max_length=10, choices=BillingIntervalChoices.choices,
        default=BillingIntervalChoices.MONTHLY,
    )
    is_active = models.BooleanField(default=True)
    is_self_serve = models.BooleanField(
        default=True,
        help_text='False for Government/EMIS — those go through sales, not self-onboarding'
    )
    included_features = models.JSONField(
        default=list, blank=True,
        help_text='List of short strings shown as checkmarks on the pricing page'
    )
    not_included = models.JSONField(
        default=list, blank=True,
        help_text='Honest trade-offs shown on the pricing page — what this tier does NOT cover'
    )

    class Meta:
        db_table = 'platform_billing_plan'
        ordering = ['base_price']

    def __str__(self):
        return self.name

    def price_for_student_count(self, student_count: int):
        """Base price plus per-student overage beyond included_students."""
        if self.included_students is None or student_count <= self.included_students:
            return self.base_price
        extra = student_count - self.included_students
        return self.base_price + (extra * self.price_per_extra_student)


class PlatformInvoice(TenantModel):
    """One invoice per tenant per billing period. Immutable once ISSUED."""
    class StatusChoices(models.TextChoices):
        DRAFT     = 'draft',     'Draft'
        ISSUED    = 'issued',    'Issued'
        PAID      = 'paid',      'Paid'
        FAILED    = 'failed',    'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    invoice_number = models.CharField(max_length=30, unique=True, blank=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='invoices')

    period_start = models.DateField()
    period_end = models.DateField()
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Snapshot of what was owed for this period — does not change if Plan pricing changes later'
    )
    status = models.CharField(max_length=15, choices=StatusChoices.choices, default=StatusChoices.ISSUED)

    issued_date = models.DateField(default=timezone.now)
    paid_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'platform_billing_invoice'
        ordering = ['-issued_date']

    def __str__(self):
        return f'{self.invoice_number} — {self.tenant.name} — {self.period_start:%b %Y}'

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = f'PLAT-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}'
        super().save(*args, **kwargs)


class PlatformPayment(TenantModel):
    """Immutable payment record settling a PlatformInvoice. One invoice, one payment (no partials)."""
    class MethodChoices(models.TextChoices):
        PESAPAL_CARD  = 'pesapal_card', 'Card (PesaPal)'
        MTN_MOMO      = 'mtn_momo',     'MTN Mobile Money'
        AIRTEL_MONEY  = 'airtel',       'Airtel Money'
        BANK_TRANSFER = 'bank',         'Bank Transfer'
        MANUAL        = 'manual',       'Manual / Platform Admin'

    receipt_number = models.CharField(max_length=30, unique=True, blank=True)
    invoice = models.ForeignKey(PlatformInvoice, on_delete=models.CASCADE, related_name='payments')

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=15, choices=MethodChoices.choices)
    reference = models.CharField(max_length=100, blank=True, help_text='PesaPal order_tracking_id, MoMo ref, etc.')
    is_recurring_charge = models.BooleanField(
        default=False, help_text='True if this came from PesaPal auto-debit rather than a live checkout'
    )
    raw_gateway_response = models.JSONField(default=dict, blank=True)

    payment_date = models.DateField(default=timezone.now)
    recorded_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='platform_payments_recorded'
    )

    class Meta:
        db_table = 'platform_billing_payment'
        ordering = ['-payment_date']

    def __str__(self):
        return f'{self.receipt_number} — {self.invoice.tenant.name} — UGX {self.amount:,.0f}'

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = f'PRCP-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}'
        super().save(*args, **kwargs)
        if self.invoice.status != PlatformInvoice.StatusChoices.PAID:
            self.invoice.status = PlatformInvoice.StatusChoices.PAID
            self.invoice.paid_date = self.payment_date
            self.invoice.save(update_fields=['status', 'paid_date'])


class PlatformPesaPalTransaction(TenantModel):
    """
    Gateway-side tracking for a platform subscription payment — Phase 5C.
    Mirrors apps.payments.PesaPalTransaction's shape but points at
    PlatformInvoice instead of FeeInvoice, and carries no `student` FK.
    """
    class StatusChoices(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED    = 'failed',    'Failed'
        REVERSED  = 'reversed',  'Reversed'

    merchant_reference = models.CharField(max_length=100, unique=True, blank=True)
    invoice = models.ForeignKey(PlatformInvoice, on_delete=models.CASCADE, related_name='pesapal_transactions')
    initiated_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='platform_transactions_initiated'
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='UGX')
    status = models.CharField(max_length=15, choices=StatusChoices.choices, default=StatusChoices.PENDING)

    is_recurring_setup = models.BooleanField(
        default=False,
        help_text='True if this order enrolled the tenant in PesaPal card auto-debit'
    )
    order_tracking_id = models.CharField(max_length=100, blank=True)
    redirect_url = models.URLField(max_length=500, blank=True)
    submit_response = models.JSONField(default=dict, blank=True)
    status_response = models.JSONField(default=dict, blank=True)
    pesapal_status_code = models.IntegerField(null=True, blank=True)
    pesapal_status_message = models.CharField(max_length=200, blank=True)
    confirmation_code = models.CharField(max_length=100, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    payment_account = models.CharField(max_length=100, blank=True)

    payer_first_name = models.CharField(max_length=100, blank=True)
    payer_last_name = models.CharField(max_length=100, blank=True)
    payer_phone = models.CharField(max_length=20, blank=True)
    payer_email = models.EmailField(blank=True)

    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'platform_billing_pesapal_transaction'
        ordering = ['-initiated_at']

    def __str__(self):
        return f'{self.merchant_reference} — {self.tenant.name} — {self.status}'

    def save(self, *args, **kwargs):
        if not self.merchant_reference:
            self.merchant_reference = f'PLATPAY-{uuid.uuid4().hex[:10].upper()}'
        super().save(*args, **kwargs)

    @property
    def is_pending(self):
        return self.status == self.StatusChoices.PENDING


class FeatureFlag(TenantModel):
    """Per-tenant module enable/disable — Section 5.4's feature flag management."""
    module_name = models.CharField(max_length=50, help_text="e.g. 'lms', 'biometric_attendance', 'career_guidance'")
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'platform_billing_feature_flag'
        unique_together = [('tenant', 'module_name')]
        ordering = ['module_name']

    def __str__(self):
        return f'{self.tenant.name} — {self.module_name}: {"on" if self.enabled else "off"}'

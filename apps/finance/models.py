"""
ASMS Finance Module — Phase 1 (Manual Payments)
Fee structure, invoices, manual payment recording, receipts.
Online MoMo/Card payments are Phase 3.
"""
from django.db import models
from django.utils import timezone
from apps.core.models import TenantModel
import uuid


class FeeCategory(TenantModel):
    """E.g. Tuition, Activity Fee, Boarding, Lunch, Library"""
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    order       = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table        = 'finance_fee_category'
        ordering        = ['order', 'name']
        unique_together = [('tenant', 'name')]

    def __str__(self):
        return self.name


class FeeStructure(TenantModel):
    """
    Defines how much each class level pays per term per category.
    One structure per (level, term, category) combination.
    """
    class_level  = models.ForeignKey('students.ClassLevel', on_delete=models.CASCADE,
                                      related_name='fee_structures')
    term         = models.ForeignKey('core.Term', on_delete=models.CASCADE,
                                     related_name='fee_structures')
    category     = models.ForeignKey(FeeCategory, on_delete=models.CASCADE,
                                     related_name='fee_structures')
    amount       = models.DecimalField(max_digits=12, decimal_places=2)
    is_optional  = models.BooleanField(default=False,
                   help_text='Optional fees appear on invoice but are not mandatory')
    notes        = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table        = 'finance_fee_structure'
        unique_together = [('tenant', 'class_level', 'term', 'category')]

    def __str__(self):
        return f'{self.class_level} — {self.category} — {self.term} — UGX {self.amount:,.0f}'


class FeeInvoice(TenantModel):
    """
    One invoice per student per term.
    Lists all applicable charges. Tracks payment status.
    """
    class StatusChoices(models.TextChoices):
        DRAFT      = 'draft',    'Draft'
        ISSUED     = 'issued',   'Issued'
        PARTIAL    = 'partial',  'Partially Paid'
        PAID       = 'paid',     'Fully Paid'
        OVERDUE    = 'overdue',  'Overdue'
        WAIVED     = 'waived',   'Waived / Bursary'
        CANCELLED  = 'cancelled', 'Cancelled'

    invoice_number = models.CharField(max_length=30, unique=True, blank=True)
    student      = models.ForeignKey('students.Student', on_delete=models.CASCADE,
                                     related_name='fee_invoices')
    term         = models.ForeignKey('core.Term', on_delete=models.CASCADE,
                                     related_name='fee_invoices')
    academic_year = models.ForeignKey('core.AcademicYear', on_delete=models.CASCADE,
                                      related_name='fee_invoices')
    issued_date  = models.DateField(default=timezone.now)
    due_date     = models.DateField(null=True, blank=True)
    status       = models.CharField(max_length=15, choices=StatusChoices.choices,
                                    default=StatusChoices.ISSUED)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount     = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                   help_text='Bursary or scholarship discount applied')
    notes        = models.TextField(blank=True)
    issued_by    = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                     null=True, related_name='invoices_issued')

    class Meta:
        db_table        = 'finance_fee_invoice'
        ordering        = ['-issued_date']
        unique_together = [('student', 'term')]

    def __str__(self):
        return f'{self.invoice_number} — {self.student} — {self.term}'

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid - self.discount

    @property
    def is_overdue(self):
        if self.due_date and self.status not in ('paid', 'waived', 'cancelled'):
            return timezone.now().date() > self.due_date
        return False

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = f'INV-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}'
        # Auto-update status based on payments
        if self.amount_paid > 0:
            if self.balance_due <= 0:
                self.status = self.StatusChoices.PAID
            else:
                self.status = self.StatusChoices.PARTIAL
        super().save(*args, **kwargs)


class FeeInvoiceItem(models.Model):
    """Individual line items on an invoice."""
    invoice     = models.ForeignKey(FeeInvoice, on_delete=models.CASCADE,
                                    related_name='items')
    category    = models.ForeignKey(FeeCategory, on_delete=models.CASCADE)
    description = models.CharField(max_length=200)
    amount      = models.DecimalField(max_digits=12, decimal_places=2)
    is_optional = models.BooleanField(default=False)

    class Meta:
        db_table = 'finance_invoice_item'

    def __str__(self):
        return f'{self.invoice.invoice_number} — {self.description} — {self.amount}'


class Payment(TenantModel):
    """
    Immutable payment record. One payment can partially or fully settle an invoice.
    Phase 1: manual recording only. Phase 3 adds MoMo/card webhooks.
    """
    class MethodChoices(models.TextChoices):
        CASH          = 'cash',       'Cash'
        BANK_TRANSFER = 'bank',       'Bank Transfer'
        MTN_MOMO      = 'mtn_momo',   'MTN Mobile Money'
        AIRTEL_MONEY  = 'airtel',     'Airtel Money'
        MPESA         = 'mpesa',      'M-Pesa'
        CARD          = 'card',       'Debit / Credit Card'
        BURSARY       = 'bursary',    'Bursary / Scholarship'
        CHEQUE        = 'cheque',     'Cheque'

    receipt_number = models.CharField(max_length=30, unique=True, blank=True)
    invoice       = models.ForeignKey(FeeInvoice, on_delete=models.CASCADE,
                                      related_name='payments')
    student       = models.ForeignKey('students.Student', on_delete=models.CASCADE,
                                      related_name='payments')
    term          = models.ForeignKey('core.Term', on_delete=models.CASCADE,
                                      related_name='payments')
    amount        = models.DecimalField(max_digits=12, decimal_places=2)
    method        = models.CharField(max_length=15, choices=MethodChoices.choices,
                                     default=MethodChoices.CASH)
    reference     = models.CharField(max_length=100, blank=True,
                   help_text='Bank ref, MoMo transaction ID, cheque number')
    payment_date  = models.DateField(default=timezone.now)
    notes         = models.TextField(blank=True)
    recorded_by   = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                      null=True, related_name='payments_recorded')
    # Phase 3 — webhook fields (null until online payments enabled)
    is_online     = models.BooleanField(default=False)
    webhook_ref   = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'finance_payment'
        ordering = ['-payment_date']

    def __str__(self):
        return f'{self.receipt_number} — {self.student} — UGX {self.amount:,.0f}'

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = f'RCP-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}'
        super().save(*args, **kwargs)
        # Update invoice amount_paid
        from django.db.models import Sum
        total = Payment.objects.filter(invoice=self.invoice).aggregate(
            t=Sum('amount'))['t'] or 0
        self.invoice.amount_paid = total
        self.invoice.save()

"""
ASMS Asset & Inventory Module
Fixed asset register with auto-logged custody history, vendor records,
staff requisitions, and purchase orders.
Benchmarked from: Skyward's procurement/fund-accounting module (purchase orders,
budget approval workflow — the benchmark Spec Section 2 already cites for ASMS
finance) and Snipe-IT, the most widely deployed open-source asset register, for
its checked-out/checked-in custody history pattern.
"""
from django.db import models
from django.utils import timezone
from apps.core.models import TenantModel, TenantManager
# ══════════════════════════════════════════════════════
# ASSET REGISTER
# ══════════════════════════════════════════════════════
class AssetCategory(TenantModel):
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    objects = TenantManager()
    class Meta:
        db_table            = 'assets_category'
        ordering            = ['name']
        unique_together     = [('tenant', 'name')]
        verbose_name        = 'Asset Category'
        verbose_name_plural = 'Asset Categories'
    def __str__(self):
        return self.name
class Asset(TenantModel):
    """A single physical asset. Custody changes are auto-logged to AssetAssignmentHistory."""
    class ConditionChoices(models.TextChoices):
        NEW     = 'new',     'New'
        GOOD    = 'good',    'Good'
        FAIR    = 'fair',    'Fair'
        POOR    = 'poor',    'Poor'
        DAMAGED = 'damaged', 'Damaged'
    class StatusChoices(models.TextChoices):
        IN_USE       = 'in_use',       'In Use'
        IN_STORAGE   = 'in_storage',   'In Storage'
        UNDER_REPAIR = 'under_repair', 'Under Repair'
        DISPOSED     = 'disposed',     'Disposed'
        LOST         = 'lost',         'Lost'
    asset_tag         = models.CharField(max_length=30, help_text='Barcode/asset tag printed on the item')
    name              = models.CharField(max_length=200)
    category          = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name='assets')
    description       = models.TextField(blank=True)
    serial_number     = models.CharField(max_length=100, blank=True)
    location          = models.CharField(max_length=150, blank=True, help_text='e.g. Library, Lab 2, Staff Room')
    condition         = models.CharField(max_length=10, choices=ConditionChoices.choices,
                                          default=ConditionChoices.NEW)
    status            = models.CharField(max_length=15, choices=StatusChoices.choices,
                                          default=StatusChoices.IN_USE)
    purchase_date     = models.DateField()
    purchase_value    = models.DecimalField(max_digits=12, decimal_places=2)
    useful_life_years = models.PositiveSmallIntegerField(default=5)
    salvage_value     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    warranty_expiry   = models.DateField(null=True, blank=True)
    assigned_to       = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='assets_assigned')
    notes             = models.TextField(blank=True)
    objects = TenantManager()
    class Meta:
        db_table        = 'assets_asset'
        ordering        = ['name']
        unique_together = [('tenant', 'asset_tag')]
        verbose_name    = 'Asset'
    def __str__(self):
        return f'{self.name} ({self.asset_tag})'
    def current_book_value(self):
        """Simple straight-line depreciation estimate."""
        if not self.purchase_value or not self.useful_life_years:
            return self.purchase_value
        years_elapsed = (timezone.now().date() - self.purchase_date).days / 365.25
        annual_depreciation = (self.purchase_value - self.salvage_value) / self.useful_life_years
        depreciated = self.purchase_value - (annual_depreciation * years_elapsed)
        return max(depreciated, self.salvage_value)
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        previous_assignee_id = None
        if not is_new:
            previous_assignee_id = Asset.objects.filter(pk=self.pk).values_list(
                'assigned_to_id', flat=True
            ).first()
        super().save(*args, **kwargs)
        if self.assigned_to_id != previous_assignee_id:
            AssetAssignmentHistory.objects.filter(
                asset=self, returned_date__isnull=True
            ).update(returned_date=timezone.now().date(), condition_at_return=self.condition)
            if self.assigned_to_id:
                AssetAssignmentHistory.objects.create(
                    tenant=self.tenant, asset=self, assigned_to=self.assigned_to,
                    assigned_date=timezone.now().date(), condition_at_assignment=self.condition,
                )
class AssetAssignmentHistory(TenantModel):
    """Custody log for an Asset — mirrors Snipe-IT's checked-out/checked-in history."""
    asset                   = models.ForeignKey(Asset, on_delete=models.CASCADE,
                                                 related_name='assignment_history')
    assigned_to             = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True,
                                                 related_name='asset_assignment_history')
    assigned_date           = models.DateField()
    returned_date           = models.DateField(null=True, blank=True)
    condition_at_assignment = models.CharField(max_length=10, choices=Asset.ConditionChoices.choices, blank=True)
    condition_at_return     = models.CharField(max_length=10, choices=Asset.ConditionChoices.choices, blank=True)
    notes                   = models.TextField(blank=True)
    objects = TenantManager()
    class Meta:
        db_table            = 'assets_assignment_history'
        ordering            = ['-assigned_date']
        verbose_name        = 'Asset Assignment History'
        verbose_name_plural = 'Asset Assignment Histories'
    def __str__(self):
        return f'{self.asset} → {self.assigned_to} ({self.assigned_date})'
# ══════════════════════════════════════════════════════
# VENDORS
# ══════════════════════════════════════════════════════
class Vendor(TenantModel):
    name           = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=150, blank=True)
    phone          = models.CharField(max_length=20, blank=True)
    email          = models.EmailField(blank=True)
    address        = models.TextField(blank=True)
    notes          = models.TextField(blank=True)
    is_active      = models.BooleanField(default=True)
    objects = TenantManager()
    class Meta:
        db_table     = 'assets_vendor'
        ordering     = ['name']
        verbose_name = 'Vendor'
    def __str__(self):
        return self.name
# ══════════════════════════════════════════════════════
# REQUISITIONS & PURCHASE ORDERS
# ══════════════════════════════════════════════════════
class Requisition(TenantModel):
    """Staff request for an item/supply, reviewed before a Purchase Order is raised."""
    class StatusChoices(models.TextChoices):
        PENDING         = 'pending',          'Pending Review'
        APPROVED        = 'approved',         'Approved'
        REJECTED        = 'rejected',         'Rejected'
        CONVERTED_TO_PO = 'converted_to_po',  'Converted to Purchase Order'
    requested_by      = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True,
                                           related_name='requisitions_made')
    department        = models.ForeignKey('academics.Department', on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='requisitions')
    item_description  = models.CharField(max_length=255)
    quantity          = models.PositiveIntegerField(default=1)
    justification      = models.TextField(blank=True)
    status            = models.CharField(max_length=20, choices=StatusChoices.choices,
                                          default=StatusChoices.PENDING)
    requested_date    = models.DateField(default=timezone.now)
    reviewed_by       = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='requisitions_reviewed')
    reviewed_date     = models.DateField(null=True, blank=True)
    linked_purchase_order = models.ForeignKey('PurchaseOrder', on_delete=models.SET_NULL, null=True, blank=True,
                                               related_name='source_requisitions')
    objects = TenantManager()
    class Meta:
        db_table     = 'assets_requisition'
        ordering     = ['-requested_date']
        verbose_name = 'Requisition'
    def __str__(self):
        return f'{self.item_description} x{self.quantity} ({self.get_status_display()})'
class PurchaseOrder(TenantModel):
    class StatusChoices(models.TextChoices):
        DRAFT            = 'draft',            'Draft'
        PENDING_APPROVAL = 'pending_approval',  'Pending Approval'
        APPROVED         = 'approved',          'Approved'
        REJECTED         = 'rejected',          'Rejected'
        FULFILLED        = 'fulfilled',         'Fulfilled'
        CANCELLED        = 'cancelled',         'Cancelled'
    po_number              = models.CharField(max_length=30, blank=True)
    vendor                 = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='purchase_orders')
    status                 = models.CharField(max_length=20, choices=StatusChoices.choices,
                                               default=StatusChoices.DRAFT)
    requested_by           = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True,
                                                related_name='purchase_orders_requested')
    approved_by            = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
                                                related_name='purchase_orders_approved')
    order_date             = models.DateField(default=timezone.now)
    expected_delivery_date = models.DateField(null=True, blank=True)
    total_amount           = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                                  help_text='Recalculated from line items via recalculate_total()')
    notes                  = models.TextField(blank=True)
    objects = TenantManager()
    class Meta:
        db_table        = 'assets_purchase_order'
        ordering        = ['-order_date']
        unique_together = [('tenant', 'po_number')]
        verbose_name    = 'Purchase Order'
    def __str__(self):
        return f'PO {self.po_number or self.pk} — {self.vendor.name}'
    def save(self, *args, **kwargs):
        if not self.po_number:
            # NOTE: simple per-year counter; swap for a dedicated sequence table
            # if you ever need this safe under high concurrency.
            year = timezone.now().year
            count = PurchaseOrder.objects.filter(tenant=self.tenant, order_date__year=year).count() + 1
            self.po_number = f'PO-{year}-{count:04d}'
        super().save(*args, **kwargs)
    def recalculate_total(self):
        total = self.items.aggregate(
            total=models.Sum(models.F('quantity') * models.F('unit_price'))
        )['total'] or 0
        self.total_amount = total
        self.save(update_fields=['total_amount'])
class PurchaseOrderItem(models.Model):
    """No tenant FK here, by design — mirrors apps.finance.FeeInvoiceItem,
    which inherits tenant scoping through its parent invoice rather than carrying its own."""
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    description    = models.CharField(max_length=255)
    quantity       = models.PositiveIntegerField(default=1)
    unit_price     = models.DecimalField(max_digits=10, decimal_places=2)
    class Meta:
        db_table     = 'assets_purchase_order_item'
        verbose_name = 'Purchase Order Item'
    def __str__(self):
        return f'{self.description} x{self.quantity}'
    @property
    def line_total(self):
        return self.quantity * self.unit_price

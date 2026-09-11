from django.contrib import admin
from .models import (
    AssetCategory, Asset, AssetAssignmentHistory, Vendor,
    Requisition, PurchaseOrder, PurchaseOrderItem,
)
@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
class AssetAssignmentHistoryInline(admin.TabularInline):
    model = AssetAssignmentHistory
    extra = 0
    readonly_fields = ('assigned_to', 'assigned_date', 'returned_date',
                        'condition_at_assignment', 'condition_at_return')
@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('asset_tag', 'name', 'category', 'status', 'condition', 'assigned_to', 'current_book_value')
    list_filter = ('status', 'condition', 'category')
    search_fields = ('asset_tag', 'name', 'serial_number')
    inlines = [AssetAssignmentHistoryInline]
@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'is_active')
    search_fields = ('name',)
@admin.register(Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    list_display = ('item_description', 'quantity', 'requested_by', 'department', 'status', 'requested_date')
    list_filter = ('status', 'department')
class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1
@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'vendor', 'status', 'total_amount', 'order_date')
    list_filter = ('status', 'vendor')
    inlines = [PurchaseOrderItemInline]

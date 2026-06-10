from django.contrib import admin
from .models import FeeCategory, FeeStructure, FeeInvoice, FeeInvoiceItem, Payment

@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'order', 'tenant']
    list_filter  = ['is_active', 'tenant']

@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['class_level', 'category', 'term', 'amount', 'tenant']
    list_filter  = ['tenant', 'term', 'class_level']

class FeeInvoiceItemInline(admin.TabularInline):
    model  = FeeInvoiceItem
    extra  = 0
    fields = ['category', 'description', 'amount', 'is_optional']

class PaymentInline(admin.TabularInline):
    model  = Payment
    extra  = 0
    fields = ['amount', 'method', 'reference', 'payment_date', 'receipt_number']
    readonly_fields = ['receipt_number']

@admin.register(FeeInvoice)
class FeeInvoiceAdmin(admin.ModelAdmin):
    list_display  = ['invoice_number', 'student', 'term', 'total_amount', 'amount_paid', 'status']
    list_filter   = ['status', 'term', 'tenant']
    search_fields = ['invoice_number', 'student__first_name', 'student__last_name']
    inlines       = [FeeInvoiceItemInline, PaymentInline]
    readonly_fields = ['invoice_number', 'balance_due']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display  = ['receipt_number', 'student', 'amount', 'method', 'payment_date', 'recorded_by']
    list_filter   = ['method', 'payment_date', 'tenant']
    search_fields = ['receipt_number', 'student__first_name', 'student__last_name']
    readonly_fields = ['receipt_number']

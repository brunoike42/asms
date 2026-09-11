from django.contrib import admin
from .models import Plan, PlatformInvoice, PlatformPayment


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'base_price', 'billing_interval', 'is_active', 'is_self_serve')
    list_filter = ('billing_interval', 'is_active', 'is_self_serve')
    search_fields = ('name', 'slug')


@admin.register(PlatformInvoice)
class PlatformInvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'tenant', 'plan', 'amount', 'status', 'issued_date', 'paid_date')
    list_filter = ('status', 'plan')
    search_fields = ('invoice_number', 'tenant__name')
    readonly_fields = ('invoice_number',)


@admin.register(PlatformPayment)
class PlatformPaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'invoice', 'amount', 'method', 'is_recurring_charge', 'payment_date')
    list_filter = ('method', 'is_recurring_charge')
    search_fields = ('receipt_number', 'invoice__invoice_number')
    readonly_fields = ('receipt_number',)

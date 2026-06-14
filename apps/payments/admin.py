from django.contrib import admin
from .models import PesaPalTransaction, IPNLog


@admin.register(PesaPalTransaction)
class PesaPalTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'merchant_reference', 'student', 'amount', 'currency',
        'status', 'payment_method', 'confirmation_code',
        'initiated_at', 'completed_at', 'tenant',
    )
    list_filter  = ('status', 'currency', 'tenant')
    search_fields = (
        'merchant_reference', 'order_tracking_id', 'confirmation_code',
        'student__first_name', 'student__last_name', 'payer_phone',
    )
    readonly_fields = (
        'merchant_reference', 'order_tracking_id', 'redirect_url',
        'submit_response', 'status_response',
        'initiated_at', 'completed_at', 'expires_at',
    )
    date_hierarchy = 'initiated_at'
    fieldsets = (
        ('Core', {
            'fields': (
                'tenant', 'invoice', 'student', 'initiated_by',
                'merchant_reference', 'order_tracking_id',
                'amount', 'currency', 'status',
            )
        }),
        ('Payer', {
            'fields': ('payer_first_name', 'payer_last_name', 'payer_phone', 'payer_email'),
        }),
        ('PesaPal Result', {
            'fields': (
                'payment_method', 'payment_account', 'confirmation_code',
                'pesapal_status_code', 'pesapal_status_message',
                'finance_payment',
            ),
        }),
        ('Raw Data', {
            'fields': ('redirect_url', 'submit_response', 'status_response'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('initiated_at', 'completed_at', 'expires_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(IPNLog)
class IPNLogAdmin(admin.ModelAdmin):
    list_display = (
        'order_tracking_id', 'order_merchant_reference',
        'notification_type', 'processed', 'received_at',
    )
    list_filter  = ('processed', 'notification_type')
    search_fields = ('order_tracking_id', 'order_merchant_reference')
    readonly_fields = ('received_at', 'processed_at', 'raw_query_string')
    date_hierarchy = 'received_at'

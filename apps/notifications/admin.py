from django.contrib import admin

from .models import SMSMessage


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "phone_e164", "status", "provider", "created_at", "delivered_at")
    list_filter = ("status", "provider", "created_at")
    search_fields = ("phone_e164", "provider_message_id", "idempotency_key")
    readonly_fields = [f.name for f in SMSMessage._meta.fields]
    date_hierarchy = "created_at"

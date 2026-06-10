from django.contrib import admin
from .models import SMSLog, Announcement

@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display  = ['recipient_phone', 'trigger', 'status', 'sent_at', 'cost', 'tenant']
    list_filter   = ['status', 'trigger', 'tenant']
    search_fields = ['recipient_phone', 'recipient_name', 'message']
    readonly_fields = ['sent_at', 'provider_ref', 'cost']

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display  = ['title', 'audience', 'is_published', 'publish_date', 'tenant']
    list_filter   = ['audience', 'is_published', 'tenant']
    search_fields = ['title', 'body']

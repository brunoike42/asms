"""
ASMS Communication Module
SMS notifications and school announcements.
Africa's Talking API for SMS delivery.
"""
from django.db import models
from django.utils import timezone
from apps.core.models import TenantModel


class SMSLog(TenantModel):
    """Audit trail for every SMS sent by the system."""
    class StatusChoices(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        SENT     = 'sent',     'Sent'
        FAILED   = 'failed',   'Failed'
        DELIVERED = 'delivered', 'Delivered'

    class TriggerChoices(models.TextChoices):
        ATTENDANCE   = 'attendance',  'Absence Notification'
        FEE_REMINDER = 'fee',         'Fee Reminder'
        RESULT       = 'result',      'Result Published'
        DISCIPLINE   = 'discipline',  'Discipline Incident'
        BULK         = 'bulk',        'Bulk Announcement'
        MANUAL       = 'manual',      'Manual / Admin'

    recipient_phone = models.CharField(max_length=20)
    recipient_name  = models.CharField(max_length=200, blank=True)
    message         = models.TextField()
    trigger         = models.CharField(max_length=20, choices=TriggerChoices.choices,
                                       default=TriggerChoices.MANUAL)
    status          = models.CharField(max_length=15, choices=StatusChoices.choices,
                                       default=StatusChoices.PENDING)
    sent_at         = models.DateTimeField(null=True, blank=True)
    provider_ref    = models.CharField(max_length=100, blank=True,
                    help_text='Africa\'s Talking message ID')
    cost            = models.DecimalField(max_digits=8, decimal_places=4, default=0,
                    help_text='Cost in USD as billed by Africa\'s Talking')
    related_student = models.ForeignKey('students.Student', on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='sms_logs')
    sent_by         = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='sms_sent')
    error_message   = models.TextField(blank=True)

    class Meta:
        db_table = 'communication_sms_log'
        ordering = ['-created_at']

    def __str__(self):
        return f'SMS to {self.recipient_phone} ({self.get_trigger_display()}) — {self.get_status_display()}'


class Announcement(TenantModel):
    """School-wide or class-specific announcements."""
    class AudienceChoices(models.TextChoices):
        ALL       = 'all',       'Everyone (All Parents & Students)'
        PARENTS   = 'parents',   'All Parents'
        STUDENTS  = 'students',  'All Students'
        STAFF     = 'staff',     'All Staff'
        CLASS     = 'class',     'Specific Class'

    title      = models.CharField(max_length=200)
    body       = models.TextField()
    audience   = models.CharField(max_length=15, choices=AudienceChoices.choices,
                                  default=AudienceChoices.ALL)
    target_class = models.ForeignKey('students.ClassRoom', on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='announcements')
    send_sms   = models.BooleanField(default=False,
                help_text='Also send as SMS to relevant phone numbers')
    is_published = models.BooleanField(default=True)
    published_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                     null=True, related_name='announcements_made')
    publish_date = models.DateTimeField(default=timezone.now)
    expires_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'communication_announcement'
        ordering = ['-publish_date']

    def __str__(self):
        return self.title

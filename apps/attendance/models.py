"""
ASMS Attendance Module
Daily attendance tracking per student.
This data feeds directly into the Early Intervention Engine.
Every absence triggers: parent SMS + risk score update.
"""
from django.db import models
from django.utils import timezone
from apps.core.models import TenantModel

import secrets


class BiometricDevice(TenantModel):
    """
    One row per physical fingerprint/biometric device deployed at a school.
    A tenant can have multiple devices (one per gate, per classroom block, etc).
    The secret_key is used to verify HMAC-SHA256 signed requests from the device
    (or from the middleware/agent software running the device, e.g. ZKTeco SDK bridge).
    """
    class DeviceType(models.TextChoices):
        ZKTECO   = 'ZKTECO', 'ZKTeco'
        SUPREMA  = 'SUPREMA', 'Suprema'
        ANVIZ    = 'ANVIZ', 'Anviz'
        OTHER    = 'OTHER', 'Other / Generic'

    class DeviceStatus(models.TextChoices):
        ACTIVE      = 'ACTIVE', 'Active'
        INACTIVE    = 'INACTIVE', 'Inactive'
        MAINTENANCE = 'MAINTENANCE', 'Under Maintenance'

    name          = models.CharField(max_length=100)
    device_type   = models.CharField(max_length=20, choices=DeviceType.choices,
                                     default=DeviceType.OTHER)
    serial_number = models.CharField(max_length=100, blank=True)
    location      = models.CharField(max_length=150, blank=True,
                                     help_text='e.g. "Main Gate", "Block A Entrance"')
    classroom     = models.ForeignKey('students.ClassRoom', on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='biometric_devices')
    secret_key    = models.CharField(max_length=64, editable=False)
    status        = models.CharField(max_length=20, choices=DeviceStatus.choices,
                                     default=DeviceStatus.ACTIVE)
    last_seen_at  = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'biometric_device'
        verbose_name = 'Biometric Device'

    def __str__(self):
        return f'{self.name} ({self.get_device_type_display()})'

    def save(self, *args, **kwargs):
        if not self.secret_key:
            self.secret_key = secrets.token_hex(32)  # 64-char hex secret
        super().save(*args, **kwargs)

    def mark_seen(self):
        self.last_seen_at = timezone.now()
        self.save(update_fields=['last_seen_at'])


class BiometricTemplate(TenantModel):
    """
    Maps a student to their enrolled fingerprint template ID on a specific device
    (or a device-agnostic template ID if your SDK issues global IDs).
    A student may be enrolled on multiple devices (e.g. main gate + classroom block).
    """
    student        = models.ForeignKey('students.Student', on_delete=models.CASCADE,
                                       related_name='biometric_templates')
    device         = models.ForeignKey(BiometricDevice, on_delete=models.CASCADE,
                                       related_name='templates')
    template_id    = models.CharField(max_length=100,
                                      help_text='Fingerprint/template ID as issued by the device SDK')
    enrolled_at    = models.DateTimeField(auto_now_add=True)
    is_active      = models.BooleanField(default=True)

    class Meta:
        db_table        = 'biometric_template'
        unique_together = [('device', 'template_id')]
        verbose_name    = 'Biometric Template'

    def __str__(self):
        return f'{self.student} on {self.device}'


class BiometricScanLog(TenantModel):
    """
    Immutable audit log of every raw scan event received from a device.
    Retained for 2 years per Section 16.3 (Audit Logs — Biometric audit).
    This is separate from AttendanceRecord: a scan log entry is written for
    EVERY scan received, even duplicates, failed matches, or out-of-window scans.
    AttendanceRecord is the derived/processed result.
    """
    class ScanResult(models.TextChoices):
        MATCHED       = 'MATCHED', 'Matched — Attendance Recorded'
        DUPLICATE     = 'DUPLICATE', 'Duplicate Scan (already marked today)'
        UNKNOWN       = 'UNKNOWN', 'Unknown Template ID'
        OUT_OF_WINDOW = 'OUT_OF_WINDOW', 'Outside Attendance Window'
        INVALID_SIG   = 'INVALID_SIG', 'Invalid Signature — Rejected'

    device          = models.ForeignKey(BiometricDevice, on_delete=models.CASCADE,
                                        related_name='scan_logs')
    student         = models.ForeignKey('students.Student', on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='biometric_scans')
    template_id_raw = models.CharField(max_length=100, blank=True)
    scanned_at      = models.DateTimeField(help_text='Timestamp reported by the device')
    received_at     = models.DateTimeField(auto_now_add=True, help_text='When ASMS received it')
    result          = models.CharField(max_length=20, choices=ScanResult.choices)
    attendance_record = models.ForeignKey('AttendanceRecord', on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name='biometric_scans')
    raw_payload     = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table     = 'biometric_scan_log'
        ordering     = ['-received_at']
        verbose_name = 'Biometric Scan Log'
        indexes = [
            models.Index(fields=['device', 'received_at']),
            models.Index(fields=['student', 'scanned_at']),
        ]

    def __str__(self):
        return f'{self.device} â€” {self.get_result_display()} â€” {self.received_at}'




class AttendanceRecord(TenantModel):
    """
    One record per student per school day.
    The most important data source for the dropout risk engine.
    """
    class StatusChoices(models.TextChoices):
        PRESENT  = 'P', 'Present'
        ABSENT   = 'A', 'Absent'
        LATE     = 'L', 'Late / Tardy'
        EXCUSED  = 'E', 'Excused Absence'
        SUSPENDED = 'S', 'Suspended'

    student      = models.ForeignKey('students.Student', on_delete=models.CASCADE,
                                     related_name='attendance_records')
    classroom    = models.ForeignKey('students.ClassRoom', on_delete=models.CASCADE,
                                     related_name='attendance_records')
    date         = models.DateField(default=timezone.now)
    status       = models.CharField(max_length=1, choices=StatusChoices.choices,
                                    default=StatusChoices.PRESENT)
    marked_by    = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                     null=True, related_name='attendance_marks')
    marked_at    = models.DateTimeField(auto_now_add=True)
    notes        = models.CharField(max_length=200, blank=True)
    excuse_reason = models.CharField(max_length=200, blank=True)
    parent_notified = models.BooleanField(default=False)
    notification_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table        = 'attendance_record'
        ordering        = ['-date', 'student__last_name']
        unique_together = [('student', 'date')]
        verbose_name    = 'Attendance Record'

    def __str__(self):
        return f'{self.student} — {self.date} — {self.get_status_display()}'

    def is_absent(self):
        return self.status == self.StatusChoices.ABSENT

    @classmethod
    def get_or_create_for_class(cls, classroom, date, marked_by):
        """
        Gets or creates attendance records for all students in a class on a given date.
        Returns list of (record, created) tuples.
        """
        from apps.students.models import Enrollment
        enrollments = Enrollment.objects.filter(
            classroom=classroom, is_active=True
        ).select_related('student')
        results = []
        for enrollment in enrollments:
            record, created = cls.objects.get_or_create(
                tenant=classroom.tenant,
                student=enrollment.student,
                date=date,
                defaults={
                    'classroom': classroom,
                    'marked_by': marked_by,
                    'status': cls.StatusChoices.PRESENT,
                }
            )
            results.append((record, created))
        return results


class AttendanceSummary(TenantModel):
    """
    Pre-computed attendance summary per student per term.
    Updated after each register marking. Used by the risk engine.
    """
    student       = models.ForeignKey('students.Student', on_delete=models.CASCADE,
                                      related_name='attendance_summaries')
    term          = models.ForeignKey('core.Term', on_delete=models.CASCADE,
                                      related_name='attendance_summaries')
    total_days    = models.PositiveSmallIntegerField(default=0)
    days_present  = models.PositiveSmallIntegerField(default=0)
    days_absent   = models.PositiveSmallIntegerField(default=0)
    days_late     = models.PositiveSmallIntegerField(default=0)
    days_excused  = models.PositiveSmallIntegerField(default=0)
    attendance_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    consecutive_absences = models.PositiveSmallIntegerField(default=0)
    last_updated  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'attendance_summary'
        unique_together = [('student', 'term')]

    def __str__(self):
        return f'{self.student} — {self.term} — {self.attendance_pct}%'

    def update_from_records(self):
        """Recompute all fields from raw AttendanceRecord data."""
        from django.db.models import Count
        records = AttendanceRecord.objects.filter(
            student=self.student,
            date__gte=self.term.start_date,
            date__lte=self.term.end_date,
        )
        self.total_days   = records.count()
        self.days_present = records.filter(status='P').count()
        self.days_absent  = records.filter(status='A').count()
        self.days_late    = records.filter(status='L').count()
        self.days_excused = records.filter(status='E').count()
        if self.total_days > 0:
            self.attendance_pct = round(
                (self.days_present + self.days_late) / self.total_days * 100, 2
            )
        # Count consecutive absences (last N records all absent)
        recent = list(records.order_by('-date').values_list('status', flat=True)[:10])
        consec = 0
        for s in recent:
            if s == 'A':
                consec += 1
            else:
                break
        self.consecutive_absences = consec
        self.save()

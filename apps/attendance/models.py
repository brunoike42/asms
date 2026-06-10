"""
ASMS Attendance Module
Daily attendance tracking per student.
This data feeds directly into the Early Intervention Engine.
Every absence triggers: parent SMS + risk score update.
"""
from django.db import models
from django.utils import timezone
from apps.core.models import TenantModel


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

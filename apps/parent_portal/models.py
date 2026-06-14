"""
Parent Portal models.

Benchmarked against:
  ClassDojo        — activity feed, instant behaviour alerts, parent messaging
  PowerSchool      — grade trend charts, teacher comments, notification centre
  Infinite Campus  — meeting booking, multi-child switcher, progress monitoring
  FACTS            — instalment plans, payment history, fee statements
  FamilyID         — emergency contacts, digital consent forms, health records
  Seesaw           — student portfolio, work samples, achievement wall
  Class Charts     — assignment calendar, seating, homework tracker
"""
from django.db import models
from django.conf import settings
from django.utils import timezone

from apps.core.models import TenantModel


class ParentMeetingBooking(TenantModel):
    """
    Parent books a slot to meet a teacher or school admin.
    Benchmarked from: Infinite Campus, PowerSchool, SchoolStatus.
    """

    STATUS_CHOICES = [
        ('pending',   'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('no_show',   'Parent Did Not Attend'),
    ]

    MEETING_TYPE_CHOICES = [
        ('academic_progress',   'Academic Progress Discussion'),
        ('behaviour_concern',   'Behaviour / Discipline Concern'),
        ('welfare_check',       'Welfare / Wellbeing Check-in'),
        ('fee_discussion',      'Fee / Financial Discussion'),
        ('general',             'General / Other'),
        ('special_needs',       'Special Educational Needs'),
        ('transition',          'Transition / Subject Choice'),
    ]

    student       = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='meeting_bookings')
    parent_user   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='meeting_bookings')
    teacher       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='meeting_slots')

    meeting_type  = models.CharField(max_length=30, choices=MEETING_TYPE_CHOICES, default='general')
    preferred_date = models.DateField()
    preferred_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=20)
    location      = models.CharField(max_length=100, blank=True, default='School Office')
    video_link    = models.URLField(blank=True, help_text='Zoom/Meet link if online meeting')

    parent_notes  = models.TextField(blank=True, help_text='What the parent wants to discuss')
    admin_notes   = models.TextField(blank=True, help_text='Internal notes for staff')
    meeting_minutes = models.TextField(blank=True, help_text='Summary recorded after meeting')

    status        = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    confirmed_at  = models.DateTimeField(null=True, blank=True)
    completed_at  = models.DateTimeField(null=True, blank=True)

    # Parent rating after meeting (Benchmarked: PowerSchool, Alma)
    parent_rating = models.PositiveIntegerField(null=True, blank=True, help_text='1–5 stars')
    parent_feedback = models.TextField(blank=True)

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-preferred_date', '-preferred_time']

    def __str__(self):
        return f'Meeting: {self.student} with {self.teacher} on {self.preferred_date}'


class AbsenceExcuse(TenantModel):
    """
    Parent submits a reason for their child's absence.
    Benchmarked from: Infinite Campus, PowerSchool, Alma — all support parent-submitted excuses.
    """

    EXCUSE_TYPE_CHOICES = [
        ('illness',          'Illness / Medical'),
        ('family_emergency', 'Family Emergency'),
        ('bereavement',      'Bereavement'),
        ('medical_appointment', 'Medical / Dental Appointment'),
        ('religious',        'Religious Observance'),
        ('travel',           'Family Travel'),
        ('other',            'Other'),
    ]

    STATUS_CHOICES = [
        ('submitted', 'Submitted — Awaiting Review'),
        ('approved',  'Approved by School'),
        ('rejected',  'Rejected'),
    ]

    student         = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='absence_excuses')
    parent_user     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='submitted_excuses')
    absence_date    = models.DateField()
    absence_date_end = models.DateField(null=True, blank=True, help_text='For multi-day absences')

    excuse_type     = models.CharField(max_length=30, choices=EXCUSE_TYPE_CHOICES)
    explanation     = models.TextField()
    supporting_doc  = models.FileField(upload_to='excuses/%Y/%m/', null=True, blank=True, help_text='Medical certificate, etc.')

    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='submitted')
    reviewed_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_excuses')
    reviewed_at     = models.DateTimeField(null=True, blank=True)
    school_response = models.TextField(blank=True)

    # Link to attendance record(s) this excuse covers
    attendance_record = models.ForeignKey(
        'attendance.AttendanceRecord', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='excuses'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-absence_date']

    def __str__(self):
        return f'Excuse: {self.student} — {self.absence_date} ({self.excuse_type})'


class ParentNotification(TenantModel):
    """
    Notification record for parent portal.
    Benchmarked from: ClassDojo (instant alerts), PowerSchool (notification centre),
    Infinite Campus (push + in-app), Remind (messaging).
    """

    CATEGORY_CHOICES = [
        ('attendance',   'Attendance Alert'),
        ('academic',     'Academic / Grades'),
        ('behaviour',    'Behaviour Incident'),
        ('merit',        'Merit / Achievement'),
        ('finance',      'Fee / Payment'),
        ('welfare',      'Welfare'),
        ('announcement', 'School Announcement'),
        ('meeting',      'Meeting'),
        ('assignment',   'Assignment'),
        ('system',       'System'),
    ]

    parent_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='parent_notifications')
    student     = models.ForeignKey('students.Student', on_delete=models.CASCADE, null=True, blank=True, related_name='parent_notifications')
    category    = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='system')
    title       = models.CharField(max_length=200)
    body        = models.TextField()
    action_url  = models.CharField(max_length=300, blank=True, help_text='Portal URL to deep-link to')
    is_read     = models.BooleanField(default=False)
    read_at     = models.DateTimeField(null=True, blank=True)
    is_urgent   = models.BooleanField(default=False)
    sms_sent    = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['parent_user', 'is_read'])]

    def __str__(self):
        return f'[{self.category}] {self.title} → {self.parent_user}'

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class ActivityPost(TenantModel):
    """
    Teacher posts an update/moment to the class feed visible to parents.
    Benchmarked from: ClassDojo (class story), Seesaw (learning feed),
    Brightwheel (daily activity), Google Classroom (stream).
    """

    POST_TYPE_CHOICES = [
        ('announcement',  'Class Announcement'),
        ('achievement',   'Student Achievement'),
        ('reminder',      'Homework / Reminder'),
        ('photo_update',  'Photo Update'),
        ('event',         'Upcoming Event'),
        ('resource',      'Learning Resource'),
        ('health_update', 'Health / Safety Update'),
    ]

    AUDIENCE_CHOICES = [
        ('class',    'Whole Class'),
        ('student',  'Specific Student (and parent)'),
        ('school',   'Whole School'),
    ]

    posted_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activity_posts')
    classroom   = models.ForeignKey('students.ClassRoom', on_delete=models.CASCADE, null=True, blank=True, related_name='activity_posts')
    student     = models.ForeignKey('students.Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_posts')
    post_type   = models.CharField(max_length=20, choices=POST_TYPE_CHOICES, default='announcement')
    audience    = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default='class')
    title       = models.CharField(max_length=200)
    body        = models.TextField()
    image       = models.ImageField(upload_to='activity_posts/%Y/%m/', null=True, blank=True)
    image_url   = models.URLField(blank=True)
    action_link = models.URLField(blank=True)
    is_pinned   = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f'{self.get_post_type_display()}: {self.title}'


class ConsentForm(TenantModel):
    """
    Digital consent form sent to parents for trips, health procedures, photos, etc.
    Benchmarked from: FamilyID, SchoolStatus, ParentPay.
    """

    FORM_TYPE_CHOICES = [
        ('school_trip',      'School Trip / Excursion'),
        ('photo_consent',    'Photography / Media Consent'),
        ('medical_treatment','Medical Treatment Consent'),
        ('data_processing',  'Data Processing Consent'),
        ('activity',         'Activity Participation'),
        ('other',            'Other'),
    ]

    title           = models.CharField(max_length=200)
    form_type       = models.CharField(max_length=20, choices=FORM_TYPE_CHOICES)
    description     = models.TextField()
    deadline        = models.DateField()
    is_active       = models.BooleanField(default=True)
    target_classes  = models.ManyToManyField('students.ClassRoom', blank=True)
    created_by      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_consent_forms')
    created_at      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.title} (due {self.deadline})'


class ConsentResponse(models.Model):
    """Parent's response to a consent form."""

    form        = models.ForeignKey(ConsentForm, on_delete=models.CASCADE, related_name='responses')
    student     = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='consent_responses')
    parent_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='consent_responses')
    consented   = models.BooleanField()
    notes       = models.TextField(blank=True)
    signed_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['form', 'student']

    def __str__(self):
        answer = 'Yes' if self.consented else 'No'
        return f'{self.student} — {self.form.title}: {answer}'

from django.conf import settings

class ParentMessage(models.Model):
    """Simple parent ↔ teacher / school messaging."""
    tenant    = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    sender    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='pp_sent')
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='pp_received')
    student   = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE,
        null=True, blank=True, related_name='parent_messages')
    subject   = models.CharField(max_length=200)
    body      = models.TextField()
    is_read   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'parent_portal_message'

    def __str__(self):
        return f"{self.sender} → {self.recipient}: {self.subject[:40]}"

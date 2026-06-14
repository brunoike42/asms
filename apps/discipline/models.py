from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import random
import string

from apps.core.models import TenantModel


def generate_incident_ref():
    year = timezone.now().year
    suffix = ''.join(random.choices(string.digits, k=5))
    return f'DIS-{year}-{suffix}'


class DisciplineCategory(TenantModel):
    """Pre-defined and tenant-customisable categories for incident classification."""

    SEVERITY_CHOICES = [
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('serious', 'Serious'),
        ('critical', 'Critical'),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    default_severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='minor')
    requires_principal_approval = models.BooleanField(
        default=False,
        help_text='Whether incidents in this category automatically require principal sign-off'
    )
    triggers_counselling = models.BooleanField(
        default=False,
        help_text='Whether a single incident in this category opens a counselling flag'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Discipline Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class DisciplineIncident(TenantModel):
    """Core record for any student behaviour incident."""

    STATUS_CHOICES = [
        ('pending_review', 'Pending Review'),
        ('under_investigation', 'Under Investigation'),
        ('awaiting_parent_response', 'Awaiting Parent Response'),
        ('awaiting_principal_approval', 'Awaiting Principal Approval'),
        ('consequence_applied', 'Consequence Applied'),
        ('appealed', 'Under Appeal'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    SEVERITY_CHOICES = [
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('serious', 'Serious'),
        ('critical', 'Critical'),
    ]

    LOCATION_CHOICES = [
        ('classroom', 'Classroom'),
        ('playground', 'Playground / Sports Field'),
        ('corridor', 'Corridor / Walkway'),
        ('canteen', 'Canteen / Dining Hall'),
        ('library', 'Library'),
        ('toilets', 'Toilets / Bathrooms'),
        ('school_gate', 'School Gate / Entrance'),
        ('dormitory', 'Dormitory / Boarding'),
        ('laboratory', 'Laboratory'),
        ('bus', 'School Bus / Transport'),
        ('off_campus', 'Off Campus'),
        ('online', 'Online / Social Media'),
        ('other', 'Other'),
    ]

    NOTIFICATION_METHOD_CHOICES = [
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('phone_call', 'Phone Call'),
        ('in_person', 'In Person'),
        ('letter', 'Written Letter'),
        ('portal', 'Parent Portal'),
    ]

    reference_number = models.CharField(max_length=30, unique=True, editable=False, db_index=True)
    academic_year = models.ForeignKey(
        'core.AcademicYear', on_delete=models.PROTECT,
        null=True, blank=True, related_name='discipline_incidents'
    )
    term = models.ForeignKey(
        'core.Term', on_delete=models.PROTECT,
        null=True, blank=True, related_name='discipline_incidents'
    )

    student = models.ForeignKey(
        'students.Student', on_delete=models.PROTECT, related_name='discipline_incidents'
    )
    category = models.ForeignKey(
        DisciplineCategory, on_delete=models.PROTECT, related_name='incidents'
    )

    title = models.CharField(max_length=250)
    description = models.TextField()
    incident_date = models.DateField()
    incident_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=30, choices=LOCATION_CHOICES, default='classroom')
    location_detail = models.CharField(max_length=100, blank=True)

    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='minor')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_review')

    co_accused_students = models.ManyToManyField(
        'students.Student', blank=True, related_name='co_accused_incidents'
    )

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='reported_incidents'
    )
    report_datetime = models.DateTimeField(auto_now_add=True)

    investigated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='investigated_incidents'
    )
    investigation_notes = models.TextField(blank=True)
    investigation_completed_at = models.DateTimeField(null=True, blank=True)

    requires_principal_approval = models.BooleanField(default=False)
    principal_reviewed = models.BooleanField(default=False)
    principal_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='principal_reviewed_incidents'
    )
    principal_reviewed_at = models.DateTimeField(null=True, blank=True)
    principal_notes = models.TextField(blank=True)

    parent_notified = models.BooleanField(default=False)
    parent_notified_at = models.DateTimeField(null=True, blank=True)
    parent_notified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='parent_notifications_sent'
    )
    parent_notification_method = models.CharField(
        max_length=20, choices=NOTIFICATION_METHOD_CHOICES, blank=True
    )
    parent_notification_note = models.TextField(blank=True)
    parent_acknowledged = models.BooleanField(default=False)
    parent_acknowledged_at = models.DateTimeField(null=True, blank=True)
    parent_acknowledgement_note = models.TextField(blank=True)

    is_appealed = models.BooleanField(default=False)
    appeal_lodged_at = models.DateTimeField(null=True, blank=True)
    appeal_lodged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lodged_appeals'
    )
    appeal_reason = models.TextField(blank=True)
    appeal_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_appeals'
    )
    appeal_reviewed_at = models.DateTimeField(null=True, blank=True)
    appeal_outcome = models.TextField(blank=True)
    appeal_upheld = models.BooleanField(null=True, blank=True)

    counselling_flag_raised = models.BooleanField(default=False)
    counselling_case = models.ForeignKey(
        'counselling.WelfareCase', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='linked_incidents'
    )

    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resolved_incidents'
    )
    resolution_summary = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-incident_date', '-report_datetime']
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['status']),
            models.Index(fields=['severity']),
            models.Index(fields=['incident_date']),
        ]

    def __str__(self):
        return f'{self.reference_number} — {self.student} ({self.category})'

    def save(self, *args, **kwargs):
        if not self.reference_number:
            for _ in range(10):
                ref = generate_incident_ref()
                if not DisciplineIncident.objects.filter(reference_number=ref).exists():
                    self.reference_number = ref
                    break
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.status not in ('resolved', 'closed')

    @property
    def days_open(self):
        if self.resolved_at:
            return (self.resolved_at.date() - self.incident_date).days
        return (timezone.now().date() - self.incident_date).days

    def get_severity_badge_class(self):
        return {
            'minor': 'bg-info',
            'moderate': 'bg-warning',
            'serious': 'bg-orange',
            'critical': 'bg-danger',
        }.get(self.severity, 'bg-secondary')

    def get_status_badge_class(self):
        return {
            'pending_review': 'bg-warning text-dark',
            'under_investigation': 'bg-primary',
            'awaiting_parent_response': 'bg-info text-dark',
            'awaiting_principal_approval': 'bg-warning text-dark',
            'consequence_applied': 'bg-secondary',
            'appealed': 'bg-secondary',
            'resolved': 'bg-success',
            'closed': 'bg-dark',
        }.get(self.status, 'bg-secondary')


class DisciplineConsequence(models.Model):
    """Formal consequence applied to a student following an incident."""

    CONSEQUENCE_TYPE_CHOICES = [
        ('verbal_warning', 'Verbal Warning'),
        ('written_warning', 'Written Warning'),
        ('detention', 'Detention'),
        ('community_service', 'Community Service'),
        ('suspension_internal', 'Internal Suspension (in school)'),
        ('suspension_external', 'External Suspension (sent home)'),
        ('expulsion', 'Expulsion'),
        ('parent_meeting', 'Parent Meeting Required'),
        ('counselling_referral', 'Counselling Referral'),
        ('demerit_points', 'Demerit Points'),
        ('privilege_withdrawal', 'Withdrawal of Privileges'),
        ('restitution', 'Restitution / Compensation'),
        ('behaviour_contract', 'Behaviour Contract'),
        ('restorative_circle', 'Restorative Circle / Mediation'),
        ('extra_duties', 'Extra School Duties'),
    ]

    APPROVAL_STATUS_CHOICES = [
        ('pending_approval', 'Pending Principal Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected by Principal'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('waived_on_appeal', 'Waived on Appeal'),
    ]

    incident = models.ForeignKey(
        DisciplineIncident, on_delete=models.CASCADE, related_name='consequences'
    )
    consequence_type = models.CharField(max_length=50, choices=CONSEQUENCE_TYPE_CHOICES)
    description = models.TextField()
    rationale = models.TextField(blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    duration_days = models.PositiveIntegerField(null=True, blank=True)
    schedule_notes = models.TextField(blank=True)

    demerit_points = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    restitution_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    restitution_description = models.TextField(blank=True)

    requires_approval = models.BooleanField(default=False)
    approval_status = models.CharField(
        max_length=25, choices=APPROVAL_STATUS_CHOICES, default='pending_approval'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_consequences'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='assigned_consequences'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='completed_consequences'
    )
    completion_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-assigned_at']

    def __str__(self):
        return f'{self.get_consequence_type_display()} — {self.incident.reference_number}'

    @property
    def is_active(self):
        return self.approval_status in ('approved', 'in_progress')


class IncidentWitness(models.Model):
    """Any person who witnessed the incident."""

    WITNESS_TYPE_CHOICES = [
        ('student', 'Student'),
        ('teaching_staff', 'Teaching Staff'),
        ('support_staff', 'Support Staff'),
        ('parent', 'Parent / Guardian'),
        ('external', 'External Party'),
    ]

    incident = models.ForeignKey(
        DisciplineIncident, on_delete=models.CASCADE, related_name='witnesses'
    )
    witness_type = models.CharField(max_length=20, choices=WITNESS_TYPE_CHOICES)
    witness_student = models.ForeignKey(
        'students.Student', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='witness_records'
    )
    witness_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='witness_records'
    )
    witness_name = models.CharField(max_length=100, blank=True)
    witness_contact = models.CharField(max_length=50, blank=True)
    statement = models.TextField(blank=True)
    statement_recorded_at = models.DateTimeField(null=True, blank=True)
    statement_recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='recorded_witness_statements'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        name = (
            str(self.witness_student) if self.witness_student
            else str(self.witness_staff) if self.witness_staff
            else self.witness_name
        )
        return f'Witness: {name} — {self.incident.reference_number}'


class IncidentEvidence(models.Model):
    """Supporting evidence or attachments for a discipline incident."""

    EVIDENCE_TYPE_CHOICES = [
        ('photo', 'Photograph'),
        ('video', 'Video Recording'),
        ('document', 'Document / Written Note'),
        ('cctv_still', 'CCTV Still'),
        ('cctv_clip', 'CCTV Clip'),
        ('written_statement', 'Written Statement'),
        ('medical_report', 'Medical / Nurse Report'),
        ('damaged_property', 'Damaged Property Record'),
        ('social_media', 'Social Media Screenshot'),
        ('other', 'Other Evidence'),
    ]

    incident = models.ForeignKey(
        DisciplineIncident, on_delete=models.CASCADE, related_name='evidence'
    )
    evidence_type = models.CharField(max_length=30, choices=EVIDENCE_TYPE_CHOICES)
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='discipline/evidence/%Y/%m/', null=True, blank=True)
    file_url = models.URLField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='uploaded_evidence'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_confidential = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.get_evidence_type_display()}: {self.title}'


class MeritRecord(TenantModel):
    """Positive recognition and merit commendations for students."""

    MERIT_TYPE_CHOICES = [
        ('academic', 'Academic Excellence'),
        ('good_behaviour', 'Good Behaviour'),
        ('leadership', 'Leadership'),
        ('community_service', 'Community Service'),
        ('sports', 'Sports Achievement'),
        ('arts_culture', 'Arts & Culture'),
        ('significant_improvement', 'Significant Improvement'),
        ('helping_peers', 'Helping Others / Peer Support'),
        ('environmental', 'Environmental Care'),
        ('school_representation', 'Represented School'),
        ('other', 'Other'),
    ]

    student = models.ForeignKey(
        'students.Student', on_delete=models.PROTECT, related_name='merit_records'
    )
    merit_type = models.CharField(max_length=30, choices=MERIT_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    merit_points = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    awarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='awarded_merits'
    )
    award_date = models.DateField()
    academic_year = models.ForeignKey(
        'core.AcademicYear', on_delete=models.PROTECT, related_name='merit_records'
    )
    term = models.ForeignKey(
        'core.Term', on_delete=models.PROTECT, related_name='merit_records'
    )
    parent_notified = models.BooleanField(default=False)
    parent_notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-award_date']

    def __str__(self):
        return f'Merit: {self.title} — {self.student}'


class StudentBehaviourSummary(TenantModel):
    """
    Pre-computed aggregate behaviour record per student per term.
    Rebuilt by signals after each incident or merit change.
    """

    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='behaviour_summaries'
    )
    term = models.ForeignKey('core.Term', on_delete=models.CASCADE)

    total_incidents = models.PositiveIntegerField(default=0)
    minor_incidents = models.PositiveIntegerField(default=0)
    moderate_incidents = models.PositiveIntegerField(default=0)
    serious_incidents = models.PositiveIntegerField(default=0)
    critical_incidents = models.PositiveIntegerField(default=0)
    total_demerit_points = models.PositiveIntegerField(default=0)
    total_merit_points = models.PositiveIntegerField(default=0)
    net_behaviour_score = models.IntegerField(default=0)
    suspensions_served = models.PositiveIntegerField(default=0)
    suspension_days = models.PositiveIntegerField(default=0)

    counselling_flag_raised = models.BooleanField(default=False)
    counselling_flag_raised_at = models.DateTimeField(null=True, blank=True)

    last_computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'term']

    def __str__(self):
        return f'{self.student} — {self.term} — {self.total_incidents} incidents'

    @property
    def behaviour_risk_contribution(self):
        """Returns 0–20 risk score contribution per spec section 3.3."""
        if self.total_incidents >= 3:
            return 20
        return round((self.total_incidents / 3) * 20)
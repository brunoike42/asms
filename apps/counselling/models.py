from django.db import models
from django.conf import settings
from django.utils import timezone
import random
import string

from apps.core.models import TenantModel


def generate_case_ref():
    year = timezone.now().year
    suffix = ''.join(random.choices(string.digits, k=5))
    return f'WEL-{year}-{suffix}'


class WelfareCase(TenantModel):

    CASE_TYPE_CHOICES = [
        ('behavioural', 'Behavioural'),
        ('academic', 'Academic Underperformance'),
        ('attendance', 'Attendance / Truancy'),
        ('financial_hardship', 'Financial Hardship'),
        ('family_circumstances', 'Family Circumstances'),
        ('mental_health', 'Mental Health & Wellbeing'),
        ('physical_health', 'Physical Health'),
        ('social_integration', 'Social Integration / Bullying'),
        ('safeguarding', 'Safeguarding Concern'),
        ('substance_abuse', 'Substance Abuse'),
        ('bereavement', 'Bereavement / Loss'),
        ('transition', 'School Transition Support'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('escalated', 'Escalated to Principal'),
        ('pending_external', 'Pending External Referral'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('monitoring', 'Closed — Monitoring'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    TRIGGER_CHOICES = [
        ('manual', 'Opened by Counsellor / Staff'),
        ('discipline', 'Auto: 3+ Discipline Incidents'),
        ('attendance', 'Auto: Attendance Below 70%'),
        ('attendance_consecutive', 'Auto: 3+ Consecutive Absences'),
        ('finance', 'Auto: Fee Arrears > 45 Days'),
        ('academic', 'Auto: Academic Failure in 2+ Subjects'),
        ('risk_score', 'Auto: Risk Score > 70'),
        ('parent_referral', 'Parent / Guardian Referral'),
        ('teacher_referral', 'Teacher Referral'),
        ('self_referral', 'Student Self-Referral'),
        ('health', 'Health / Nurse Referral'),
    ]

    reference_number = models.CharField(max_length=30, unique=True, editable=False, db_index=True)
    academic_year = models.ForeignKey(
        'core.AcademicYear', on_delete=models.PROTECT,
        null=True, blank=True, related_name='welfare_cases'
    )
    term = models.ForeignKey(
        'core.Term', on_delete=models.PROTECT,
        null=True, blank=True, related_name='welfare_cases'
    )

    student = models.ForeignKey(
        'students.Student', on_delete=models.PROTECT, related_name='welfare_cases'
    )
    case_type = models.CharField(max_length=30, choices=CASE_TYPE_CHOICES)
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    trigger = models.CharField(max_length=30, choices=TRIGGER_CHOICES, default='manual')
    auto_opened = models.BooleanField(default=False)

    risk_score_at_opening = models.PositiveIntegerField(null=True, blank=True)
    risk_signals_at_opening = models.JSONField(default=dict, blank=True)

    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='opened_cases'
    )
    assigned_counsellor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_welfare_cases'
    )
    assigned_at = models.DateTimeField(null=True, blank=True)

    escalated = models.BooleanField(default=False)
    escalated_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='escalated_welfare_cases'
    )
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_reason = models.TextField(blank=True)
    principal_response = models.TextField(blank=True)
    principal_responded_at = models.DateTimeField(null=True, blank=True)

    parent_informed = models.BooleanField(default=False)
    parent_informed_at = models.DateTimeField(null=True, blank=True)
    parent_informed_how = models.CharField(max_length=100, blank=True)
    parent_meeting_scheduled = models.BooleanField(default=False)
    parent_meeting_date = models.DateField(null=True, blank=True)
    parent_meeting_notes = models.TextField(blank=True)

    student_consent_given = models.BooleanField(default=False)
    parent_consent_given = models.BooleanField(default=False)

    next_review_date = models.DateField(null=True, blank=True)
    follow_up_notes = models.TextField(blank=True)

    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resolved_welfare_cases'
    )
    resolution_summary = models.TextField(blank=True)
    outcome = models.CharField(max_length=50, blank=True, choices=[
        ('fully_resolved', 'Fully Resolved'),
        ('partially_resolved', 'Partially Resolved'),
        ('referred_externally', 'Referred Externally'),
        ('student_left', 'Student Left School'),
        ('no_longer_relevant', 'No Longer Relevant'),
        ('escalated_authority', 'Escalated to Authorities'),
    ])

    involves_safeguarding = models.BooleanField(default=False)
    involves_abuse = models.BooleanField(default=False)
    involves_self_harm_risk = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['assigned_counsellor', 'status']),
        ]

    def __str__(self):
        return f'{self.reference_number} — {self.student} ({self.case_type})'

    def save(self, *args, **kwargs):
        if not self.reference_number:
            for _ in range(10):
                ref = generate_case_ref()
                if not WelfareCase.objects.filter(reference_number=ref).exists():
                    self.reference_number = ref
                    break
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.status in ('open', 'in_progress', 'escalated', 'pending_external')

    @property
    def days_open(self):
        end = self.resolved_at or timezone.now()
        return (end.date() - self.created_at.date()).days

    def get_priority_badge_class(self):
        return {
            'low': 'bg-secondary',
            'medium': 'bg-info text-dark',
            'high': 'bg-warning text-dark',
            'critical': 'bg-danger',
        }.get(self.priority, 'bg-secondary')

    def get_status_badge_class(self):
        return {
            'open': 'bg-primary',
            'in_progress': 'bg-info text-dark',
            'escalated': 'bg-danger',
            'pending_external': 'bg-warning text-dark',
            'resolved': 'bg-success',
            'closed': 'bg-dark',
            'monitoring': 'bg-secondary',
        }.get(self.status, 'bg-secondary')


class CounsellingSession(models.Model):

    SESSION_TYPE_CHOICES = [
        ('initial_assessment', 'Initial Assessment'),
        ('individual_counselling', 'Individual Counselling Session'),
        ('group_session', 'Group Session'),
        ('family_meeting', 'Family / Parent Meeting'),
        ('peer_mediation', 'Peer Mediation'),
        ('crisis_intervention', 'Crisis Intervention'),
        ('follow_up', 'Follow-Up Check-In'),
        ('external_referral_prep', 'External Referral Preparation'),
        ('phone_call', 'Phone Call'),
        ('home_visit', 'Home Visit'),
        ('other', 'Other'),
    ]

    MOOD_CHOICES = [
        ('positive', 'Positive / Engaged'),
        ('neutral', 'Neutral / Cooperative'),
        ('withdrawn', 'Withdrawn / Quiet'),
        ('distressed', 'Distressed / Emotional'),
        ('resistant', 'Resistant / Uncooperative'),
        ('absent', 'Did Not Attend'),
    ]

    welfare_case = models.ForeignKey(
        WelfareCase, on_delete=models.CASCADE, related_name='sessions'
    )
    session_date = models.DateField()
    session_time = models.TimeField(null=True, blank=True)
    session_type = models.CharField(max_length=30, choices=SESSION_TYPE_CHOICES, default='individual_counselling')
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)

    student_attended = models.BooleanField(default=True)
    parent_attended = models.BooleanField(default=False)
    other_attendees = models.CharField(max_length=200, blank=True)

    student_mood = models.CharField(max_length=20, choices=MOOD_CHOICES, blank=True)
    mood_notes = models.TextField(blank=True)

    session_notes = models.TextField()
    presenting_issues = models.TextField(blank=True)
    interventions_used = models.TextField(blank=True)
    progress_assessment = models.TextField(blank=True)
    actions_agreed = models.TextField(blank=True)
    counsellor_actions = models.TextField(blank=True)

    follow_up_required = models.BooleanField(default=True)
    follow_up_date = models.DateField(null=True, blank=True)
    urgency_level = models.CharField(max_length=20, choices=[
        ('routine', 'Routine'),
        ('soon', 'Within One Week'),
        ('urgent', 'Urgent (within 48 hours)'),
        ('crisis', 'Crisis — Immediate Action Required'),
    ], default='routine')

    risk_reassessment = models.TextField(blank=True)
    safeguarding_concern_raised = models.BooleanField(default=False)
    safeguarding_notes = models.TextField(blank=True)

    conducted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='conducted_sessions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-session_date', '-created_at']

    def __str__(self):
        return f'Session — {self.welfare_case.reference_number} — {self.session_date}'


class WelfareCaseAction(models.Model):

    ACTION_TYPE_CHOICES = [
        ('phone_call_parent', 'Phone Call to Parent'),
        ('sms_to_parent', 'SMS to Parent'),
        ('letter_to_parent', 'Letter to Parent'),
        ('teacher_alert', 'Class Teacher Alerted'),
        ('admin_alerted', 'Admin / Principal Alerted'),
        ('external_referral', 'External Referral Made'),
        ('fee_waiver_submitted', 'Fee Waiver Application Submitted'),
        ('bursary_applied', 'Bursary Applied'),
        ('class_change', 'Class / Group Change'),
        ('support_programme', 'Enrolled in Support Programme'),
        ('emergency_contact', 'Emergency Contact Made'),
        ('home_contact', 'Home Contact / Visit'),
        ('other', 'Other Action'),
    ]

    OUTCOME_CHOICES = [
        ('successful', 'Successful'),
        ('partial', 'Partially Successful'),
        ('unsuccessful', 'Unsuccessful'),
        ('pending', 'Pending / Awaiting Response'),
        ('no_outcome', 'No Outcome Yet'),
    ]

    welfare_case = models.ForeignKey(
        WelfareCase, on_delete=models.CASCADE, related_name='actions'
    )
    action_type = models.CharField(max_length=30, choices=ACTION_TYPE_CHOICES)
    description = models.TextField()
    action_date = models.DateField(default=timezone.now)
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, default='pending')
    outcome_notes = models.TextField(blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='welfare_actions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-action_date']

    def __str__(self):
        return f'{self.get_action_type_display()} — {self.welfare_case.reference_number}'


class BursaryApplication(TenantModel):

    WAIVER_TYPE_CHOICES = [
        ('full_waiver', 'Full Fee Waiver'),
        ('partial_waiver', 'Partial Fee Reduction'),
        ('payment_plan', 'Payment Plan / Instalment Arrangement'),
        ('bursary', 'Bursary Award'),
        ('scholarship', 'Scholarship Application'),
        ('emergency_fund', 'Emergency Hardship Fund'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Principal Approval'),
        ('approved', 'Approved'),
        ('partially_approved', 'Partially Approved'),
        ('rejected', 'Rejected'),
        ('applied_to_account', 'Applied to Student Account'),
    ]

    welfare_case = models.OneToOneField(
        WelfareCase, on_delete=models.CASCADE,
        related_name='bursary_application', null=True, blank=True
    )
    student = models.ForeignKey(
        'students.Student', on_delete=models.PROTECT, related_name='bursary_applications'
    )
    academic_year = models.ForeignKey(
        'core.AcademicYear', on_delete=models.PROTECT, null=True, blank=True
    )
    term = models.ForeignKey(
        'core.Term', on_delete=models.PROTECT, null=True, blank=True
    )

    waiver_type = models.CharField(max_length=20, choices=WAIVER_TYPE_CHOICES)
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    supporting_documents = models.FileField(
        upload_to='counselling/bursary/%Y/', null=True, blank=True
    )
    household_income_estimate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    number_of_dependants = models.PositiveIntegerField(null=True, blank=True)
    financial_circumstances = models.TextField(blank=True)
    current_fee_balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    arrears_days = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='draft')
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='submitted_bursaries'
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_bursaries'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_bursaries'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    amount_approved = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    applied_to_account_at = models.DateTimeField(null=True, blank=True)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='applied_bursaries'
    )
    finance_reference = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Bursary: {self.student} — {self.get_waiver_type_display()}'


class CounsellorReferral(models.Model):

    REFERRAL_TYPE_CHOICES = [
        ('internal_nurse', 'Internal: School Nurse'),
        ('internal_admin', 'Internal: School Admin'),
        ('external_hospital', 'External: Hospital / Clinic'),
        ('external_psychologist', 'External: Psychologist'),
        ('external_social_worker', 'External: Social Worker'),
        ('external_ngo', 'External: NGO / Community Organisation'),
        ('external_police', 'External: Police / Authorities'),
        ('external_ministry', 'External: Ministry of Education'),
        ('external_family_support', 'External: Family Support Services'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('made', 'Referral Made'),
        ('accepted', 'Accepted by Agency'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('declined', 'Declined by Agency'),
        ('student_refused', 'Student Declined'),
        ('no_response', 'No Response from Agency'),
    ]

    welfare_case = models.ForeignKey(
        WelfareCase, on_delete=models.CASCADE, related_name='referrals'
    )
    referral_type = models.CharField(max_length=30, choices=REFERRAL_TYPE_CHOICES)
    referred_to_name = models.CharField(max_length=200)
    referred_to_contact = models.CharField(max_length=100, blank=True)
    reason = models.TextField()
    referral_date = models.DateField(default=timezone.now)
    follow_up_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='made')
    outcome = models.TextField(blank=True)
    documents_sent = models.TextField(blank=True)
    made_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='made_referrals'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-referral_date']

    def __str__(self):
        return f'Referral: {self.referred_to_name} — {self.welfare_case.reference_number}'


class AtRiskRegister(TenantModel):
    """
    Pre-computed weekly at-risk register per student per term.
    Composite risk score 0-100 per spec Section 3.3 & 7.2.
    """

    RISK_LEVEL_CHOICES = [
        ('low', 'Low (0-40)'),
        ('medium', 'Medium (41-70)'),
        ('high', 'High (71-100)'),
    ]

    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='risk_registers'
    )
    term = models.ForeignKey('core.Term', on_delete=models.CASCADE)

    risk_score = models.PositiveIntegerField(default=0)
    risk_level = models.CharField(max_length=10, choices=RISK_LEVEL_CHOICES, default='low')

    # Component scores (max: attendance 30, academic 25, behaviour 20, finance 15, welfare 10)
    attendance_score = models.PositiveIntegerField(default=0)
    academic_score = models.PositiveIntegerField(default=0)
    behaviour_score = models.PositiveIntegerField(default=0)
    finance_score = models.PositiveIntegerField(default=0)
    welfare_score = models.PositiveIntegerField(default=0)

    attendance_pct = models.FloatField(default=100.0)
    failed_subjects = models.PositiveIntegerField(default=0)
    incident_count = models.PositiveIntegerField(default=0)
    fee_arrears_days = models.PositiveIntegerField(default=0)
    open_welfare_cases = models.PositiveIntegerField(default=0)

    counsellor_actioned = models.BooleanField(default=False)
    counsellor_actioned_at = models.DateTimeField(null=True, blank=True)
    alert_sent = models.BooleanField(default=False)
    alert_sent_at = models.DateTimeField(null=True, blank=True)

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'term']
        ordering = ['-risk_score']

    def __str__(self):
        return f'{self.student} — Risk: {self.risk_score}/100 ({self.risk_level})'
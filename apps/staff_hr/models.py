from django.db import models
from apps.core.models import TenantModel, TenantManager
from apps.core.models import Tenant, TenantManager
from apps.academics.models import Department
from django.conf import settings

class StaffProfile(models.Model):
    EMPLOYMENT_CHOICES = [
        ('permanent', 'Permanent'), ('contract', 'Contract'), ('probation', 'Probation'),
        ('volunteer', 'Volunteer'), ('retired', 'Retired'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='staff_profile')
    staff_no = models.CharField(max_length=20, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_CHOICES, default='permanent')
    date_joined = models.DateField(null=True, blank=True)
    national_id = models.CharField(max_length=30, blank=True)
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=30, blank=True)
    next_of_kin_name = models.CharField(max_length=200, blank=True)
    next_of_kin_phone = models.CharField(max_length=20, blank=True)
    qualifications = models.TextField(blank=True)
    specialisation = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'staff_profiles'

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.designation or self.user.role})"

class LeaveType(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    days_allowed = models.IntegerField(default=21)
    is_paid = models.BooleanField(default=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'leave_types'

    def __str__(self):
        return self.name

class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('approved', 'Approved'),
        ('rejected', 'Rejected'), ('cancelled', 'Cancelled'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'leave_requests'
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.staff} — {self.leave_type} ({self.start_date} to {self.end_date})"

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1

class CPDRecord(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='cpd_records')
    title = models.CharField(max_length=200)
    institution = models.CharField(max_length=200, blank=True)
    cpd_type = models.CharField(max_length=100, choices=[
        ('workshop', 'Workshop'), ('seminar', 'Seminar'), ('course', 'Course'),
        ('conference', 'Conference'), ('online', 'Online Training'),
    ], default='workshop')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    hours = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    certificate = models.FileField(upload_to='cpd_certificates/', blank=True, null=True)
    notes = models.TextField(blank=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'cpd_records'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.staff} — {self.title}"
# ══════════════════════════════════════════════════════
# STAFF APPRAISALS — Phase 4 addition
# Benchmarked from: Infinite Campus Staff Evaluations and Frontline Performance
# (formerly PD&E) — both use a scored-area appraisal with SMART objectives as
# child records reviewed at the next cycle, which is the pattern we replicate here.
# ══════════════════════════════════════════════════════
class StaffAppraisal(TenantModel):
    """
    Formal performance appraisal per staff member per appraisal period.
    Scored across five areas (1-5). SMART objectives are child records
    (AppraisalObjective) reviewed at the next appraisal cycle.
    """
    class StatusChoices(models.TextChoices):
        DRAFT        = "draft",        "Draft"
        SUBMITTED    = "submitted",    "Submitted to HR"
        ACKNOWLEDGED = "acknowledged", "Acknowledged by Staff"
    staff_member     = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE,
        related_name="appraisals_received"
    )
    appraiser        = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True,
        related_name="appraisals_conducted"
    )
    academic_year    = models.ForeignKey(
        "core.AcademicYear", on_delete=models.PROTECT,
        related_name="staff_appraisals"
    )
    appraisal_period = models.CharField(
        max_length=50,
        help_text="e.g. 'Annual 2024-25', 'Mid-Year Term 2 2025'"
    )
    appraisal_date   = models.DateField()
    # Scored areas — 1 (Unsatisfactory) to 5 (Excellent)
    teaching_quality  = models.PositiveSmallIntegerField(null=True, blank=True)
    punctuality       = models.PositiveSmallIntegerField(null=True, blank=True)
    student_relations = models.PositiveSmallIntegerField(null=True, blank=True)
    professional_dev  = models.PositiveSmallIntegerField(null=True, blank=True)
    teamwork          = models.PositiveSmallIntegerField(null=True, blank=True)
    strengths             = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)
    appraiser_comments    = models.TextField(blank=True)
    staff_response        = models.TextField(
        blank=True,
        help_text="Staff member can respond before the record is formally acknowledged"
    )
    status            = models.CharField(
        max_length=15, choices=StatusChoices.choices,
        default=StatusChoices.DRAFT
    )
    acknowledged_date = models.DateField(null=True, blank=True)
    objects = TenantManager()
    class Meta:
        db_table        = "staff_appraisal"
        ordering        = ["-appraisal_date"]
        unique_together = [("tenant", "staff_member", "academic_year", "appraisal_period")]
        verbose_name    = "Staff Appraisal"
    def __str__(self):
        return f"{self.staff_member} — {self.appraisal_period}"
    @property
    def average_score(self):
        scores = [s for s in [
            self.teaching_quality, self.punctuality,
            self.student_relations, self.professional_dev, self.teamwork
        ] if s is not None]
        return round(sum(scores) / len(scores), 2) if scores else None
class AppraisalObjective(TenantModel):
    """SMART objectives set during an appraisal — reviewed at the next cycle."""
    class StatusChoices(models.TextChoices):
        PENDING      = "pending",      "Pending"
        IN_PROGRESS  = "in_progress",  "In Progress"
        ACHIEVED     = "achieved",     "Achieved"
        NOT_ACHIEVED = "not_achieved", "Not Achieved"
    appraisal    = models.ForeignKey(
        StaffAppraisal, on_delete=models.CASCADE,
        related_name="objectives"
    )
    objective    = models.TextField()
    target_date  = models.DateField()
    status       = models.CharField(
        max_length=15, choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )
    evidence     = models.TextField(blank=True, help_text="Evidence provided by staff member")
    review_notes = models.TextField(blank=True, help_text="Reviewer notes at next appraisal cycle")
    objects = TenantManager()
    class Meta:
        db_table     = "staff_appraisal_objective"
        ordering     = ["target_date"]
        verbose_name = "Appraisal Objective"
    def __str__(self):
        truncated = self.objective[:60]
        return f"{truncated}... ({self.get_status_display()})"
class TrainingPlan(TenantModel):
    """
    Annual professional development plan for a staff member.
    Approved by HR/principal before items are actioned.
    completion_rate is computed from child TrainingPlanItem records.
    """
    class StatusChoices(models.TextChoices):
        DRAFT       = "draft",       "Draft"
        SUBMITTED   = "submitted",   "Submitted for Approval"
        APPROVED    = "approved",    "Approved"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED   = "completed",   "Completed"
    staff_member  = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE,
        related_name="training_plans"
    )
    academic_year = models.ForeignKey(
        "core.AcademicYear", on_delete=models.PROTECT,
        related_name="training_plans"
    )
    status        = models.CharField(
        max_length=15, choices=StatusChoices.choices,
        default=StatusChoices.DRAFT
    )
    created_by    = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True,
        related_name="training_plans_created"
    )
    approved_by   = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="training_plans_approved"
    )
    approved_date = models.DateField(null=True, blank=True)
    notes         = models.TextField(blank=True)
    objects = TenantManager()
    class Meta:
        db_table        = "staff_training_plan"
        ordering        = ["-academic_year__start_date"]
        unique_together = [("tenant", "staff_member", "academic_year")]
        verbose_name    = "Training Plan"
    def __str__(self):
        return f"{self.staff_member} — Training Plan {self.academic_year}"
    @property
    def completion_rate(self):
        total = self.items.count()
        if not total:
            return 0
        done = self.items.filter(status=TrainingPlanItem.StatusChoices.COMPLETED).count()
        return round((done / total) * 100)
class TrainingPlanItem(TenantModel):
    """Individual training activity within a plan."""
    class TrainingTypeChoices(models.TextChoices):
        INTERNAL_WORKSHOP = "internal_workshop", "Internal Workshop"
        EXTERNAL_COURSE   = "external_course",   "External Course"
        ONLINE_LEARNING   = "online_learning",   "Online Learning"
        CONFERENCE        = "conference",         "Conference / Seminar"
        MENTORING         = "mentoring",          "Peer Mentoring"
        PEER_OBSERVATION  = "peer_observation",   "Peer Observation"
        OTHER             = "other",              "Other"
    class StatusChoices(models.TextChoices):
        PLANNED   = "planned",   "Planned"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
    training_plan  = models.ForeignKey(
        TrainingPlan, on_delete=models.CASCADE,
        related_name="items"
    )
    training_title = models.CharField(max_length=255)
    training_type  = models.CharField(
        max_length=20, choices=TrainingTypeChoices.choices,
        default=TrainingTypeChoices.EXTERNAL_COURSE
    )
    provider       = models.CharField(
        max_length=200, blank=True,
        help_text="Training provider, institution, or platform name"
    )
    planned_date   = models.DateField()
    actual_date    = models.DateField(null=True, blank=True)
    duration_hours = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    cost_ugx       = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Estimated or actual cost in UGX"
    )
    status         = models.CharField(
        max_length=10, choices=StatusChoices.choices,
        default=StatusChoices.PLANNED
    )
    outcome        = models.TextField(
        blank=True,
        help_text="What was learned / achieved — filled in after completion"
    )
    objects = TenantManager()
    class Meta:
        db_table     = "staff_training_plan_item"
        ordering     = ["planned_date"]
        verbose_name = "Training Plan Item"
    def __str__(self):
        return f"{self.training_title} ({self.get_status_display()})"

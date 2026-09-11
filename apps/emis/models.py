"""
ASMS EMIS Reporting Module
School infrastructure census data and export submission tracking.
Design principle (Spec Section 6.6): every data point the ministry needs is
collected during normal school operations. EMIS export is a single-click
aggregation of data that already exists across Student, Staff, Attendance,
and infrastructure records — not a separate data-entry exercise.
Benchmarked from: Uganda MoES EMIS, Kenya MoE NEMIS, Rwanda REB census
export requirements. SchoolInfrastructureRecord covers the facilities section
of the annual census that cannot be derived from other modules.
"""
from django.db import models
from django.utils import timezone
from apps.core.models import TenantModel, TenantManager, Tenant
class SchoolInfrastructureRecord(TenantModel):
    """
    Infrastructure census data — collected once per academic year by the school admin.
    Feeds the facilities section of EMIS exports that cannot be derived from
    other modules (rooms, utilities, sanitation, labs, computers).
    """
    academic_year = models.ForeignKey(
        "core.AcademicYear", on_delete=models.PROTECT,
        related_name="infrastructure_records"
    )
    # Classrooms
    total_classrooms      = models.PositiveSmallIntegerField(default=0)
    functional_classrooms = models.PositiveSmallIntegerField(default=0)
    # Utilities
    has_electricity  = models.BooleanField(default=False)
    has_piped_water  = models.BooleanField(default=False)
    has_borehole     = models.BooleanField(default=False)
    has_internet     = models.BooleanField(default=False)
    internet_type    = models.CharField(
        max_length=50, blank=True,
        help_text="e.g. Fibre, 4G LTE, Satellite, WiMAX"
    )
    # Sanitation
    toilet_blocks_boys     = models.PositiveSmallIntegerField(default=0)
    toilet_blocks_girls    = models.PositiveSmallIntegerField(default=0)
    toilet_blocks_teachers = models.PositiveSmallIntegerField(default=0)
    # Facilities
    has_library      = models.BooleanField(default=False)
    library_books    = models.PositiveIntegerField(default=0)
    has_laboratory   = models.BooleanField(default=False)
    lab_count        = models.PositiveSmallIntegerField(default=0)
    has_computer_lab = models.BooleanField(default=False)
    computer_count   = models.PositiveSmallIntegerField(default=0)
    has_sports_field = models.BooleanField(default=False)
    last_updated_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="infrastructure_records_updated"
    )
    notes = models.TextField(blank=True)
    objects = TenantManager()
    class Meta:
        db_table        = "emis_infrastructure_record"
        unique_together = [("tenant", "academic_year")]
        verbose_name    = "School Infrastructure Record"
    def __str__(self):
        return f"Infrastructure — {self.academic_year}"
    @property
    def student_toilet_ratio(self):
        """Rough sanitation ratio — used in compliance dashboard."""
        from apps.students.models import Student
        total_students = Student.objects.filter(
            tenant=self.tenant, status="active"
        ).count()
        total_toilets = self.toilet_blocks_boys + self.toilet_blocks_girls
        if total_toilets == 0:
            return None
        return round(total_students / total_toilets)
class EMISSubmission(TenantModel):
    """
    Tracks each EMIS export event — when it was generated, by whom,
    the file path, compliance issues at export time, and the ministry
    reference number once submitted. Multiple exports per year are allowed
    (re-runs after data corrections mirror the Spec D.8 workflow).
    """
    
    class StatusChoices(models.TextChoices):
        GENERATED    = "generated",    "Export Generated"
        SUBMITTED    = "submitted",    "Submitted to Ministry"
        ACKNOWLEDGED = "acknowledged", "Acknowledged by Ministry"
    academic_year        = models.ForeignKey(
        "core.AcademicYear", on_delete=models.PROTECT,
        related_name="emis_submissions"
    )
    country_template     = models.CharField(
        max_length=20, choices=Tenant.EMISCountryChoices.choices,
        default=Tenant.EMISCountryChoices.UGANDA
    )
    generated_by         = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True,
        related_name="emis_exports_generated"
    )
    generated_at         = models.DateTimeField(default=timezone.now)
    file_path            = models.CharField(
        max_length=500, blank=True,
        help_text="Storage path / URL to the generated CSV/ZIP file"
    )
    status               = models.CharField(
        max_length=15, choices=StatusChoices.choices,
        default=StatusChoices.GENERATED
    )
    submission_reference = models.CharField(
        max_length=100, blank=True,
        help_text="Reference number provided by the ministry on receipt"
    )
    submitted_date       = models.DateField(null=True, blank=True)
    submitted_by         = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="emis_exports_submitted"
    )
    compliance_issues    = models.JSONField(
        default=list, blank=True,
        help_text="List of compliance warnings detected at export time (missing NSINs, etc.)"
    )
    notes                = models.TextField(blank=True)
    objects = TenantManager()
    class Meta:
        db_table     = "emis_submission"
        ordering     = ["-generated_at"]
        verbose_name = "EMIS Submission"
    def __str__(self):
        return (f"{self.get_country_template_display()} — "
                f"{self.academic_year} ({self.generated_at:%Y-%m-%d})")
    @property
    def compliance_issue_count(self):
        return len(self.compliance_issues) if self.compliance_issues else 0
    @property
    def is_clean(self):
        return self.compliance_issue_count == 0

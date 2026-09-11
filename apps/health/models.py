"""
ASMS Health Module
Persistent student medical record, nurse visit log, medication dispensing,
and vaccination tracking.
Benchmarked from: Infinite Campus Health (most comprehensive K-12 health record
system in North America) and PowerSchool Health — both use a two-layer architecture:
a persistent StudentHealthRecord (allergies, chronic conditions, emergency contacts,
doctor details) separate from episodic NurseVisit records. We replicate that pattern
exactly here.
Note: ConsentForm and ConsentResponse already exist in apps.parent_portal and are
not duplicated here. The parent portal health section references those directly.
"""
from django.db import models
from django.utils import timezone
from apps.core.models import TenantModel, TenantManager
# ══════════════════════════════════════════════════════
# PERSISTENT MEDICAL PROFILE
# ══════════════════════════════════════════════════════
class StudentHealthRecord(TenantModel):
    """
    One persistent record per student — auto-created on Student creation (signals.py).
    Visible to: Nurse, Counsellor, Principal. NOT visible to general teaching staff
    (access control enforced at the view layer).
    Cross-module link: allergies field is referenced by apps.canteen.MenuItem.contains_allergens
    to alert canteen staff before serving a flagged student.
    """
    class BloodTypeChoices(models.TextChoices):
        A_POS   = "A+",      "A+"
        A_NEG   = "A-",      "A-"
        B_POS   = "B+",      "B+"
        B_NEG   = "B-",      "B-"
        AB_POS  = "AB+",     "AB+"
        AB_NEG  = "AB-",     "AB-"
        O_POS   = "O+",      "O+"
        O_NEG   = "O-",      "O-"
        UNKNOWN = "unknown",  "Unknown"
    student = models.OneToOneField(
        "students.Student", on_delete=models.CASCADE,
        related_name="health_record"
    )
    # ── Medical ──────────────────────────────────────
    blood_type = models.CharField(
        max_length=10, choices=BloodTypeChoices.choices,
        default=BloodTypeChoices.UNKNOWN
    )
    allergies = models.TextField(
        blank=True,
        help_text="Known allergies — cross-checked against canteen MenuItem.contains_allergens"
    )
    chronic_conditions = models.TextField(
        blank=True,
        help_text="e.g. asthma, diabetes, epilepsy, sickle cell — informs teacher and nurse response"
    )
    physical_disabilities = models.TextField(blank=True)
    is_on_regular_medication = models.BooleanField(default=False)
    regular_medication_details = models.TextField(
        blank=True,
        help_text="Name, dosage, and schedule of ongoing daily medications"
    )
    special_dietary_requirements = models.TextField(
        blank=True,
        help_text="Medical dietary needs — surfaced on canteen weekly menu for flagged students"
    )
    # ── Emergency Contacts ───────────────────────────
    # Separate from Guardian — may be a different trusted adult (aunt, neighbour, etc.)
    emergency_contact_1_name         = models.CharField(max_length=150, blank=True)
    emergency_contact_1_phone        = models.CharField(max_length=20, blank=True)
    emergency_contact_1_relationship = models.CharField(max_length=50, blank=True)
    emergency_contact_2_name         = models.CharField(max_length=150, blank=True)
    emergency_contact_2_phone        = models.CharField(max_length=20, blank=True)
    emergency_contact_2_relationship = models.CharField(max_length=50, blank=True)
    # ── Medical Provider ─────────────────────────────
    doctor_name               = models.CharField(max_length=150, blank=True)
    doctor_phone              = models.CharField(max_length=20, blank=True)
    hospital_preference       = models.CharField(
        max_length=200, blank=True,
        help_text="Preferred hospital or clinic in case of emergency"
    )
    medical_insurance_provider = models.CharField(max_length=150, blank=True)
    medical_insurance_number   = models.CharField(max_length=100, blank=True)
    notes           = models.TextField(blank=True)
    last_updated_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="health_records_updated"
    )
    objects = TenantManager()
    class Meta:
        db_table     = "health_student_health_record"
        verbose_name = "Student Health Record"
    def __str__(self):
        return f"Health Record — {self.student}"
    @property
    def has_critical_alerts(self):
        """True if the student has any condition needing immediate awareness."""
        return bool(self.allergies or self.chronic_conditions or self.physical_disabilities)
    @property
    def vaccinations_due(self):
        """Returns any vaccination records with a next_due_date in the past or today."""
        today = timezone.now().date()
        return self.student.vaccination_records.filter(
            next_due_date__lte=today
        )
# ══════════════════════════════════════════════════════
# NURSE VISITS (EPISODIC)
# ══════════════════════════════════════════════════════
class NurseVisit(TenantModel):
    """
    One record per nurse room episode — complaint → assessment → action → follow-up.
    Mirrors the Infinite Campus Health visit record structure.
    Medication dispensed during the visit is recorded in MedicationDispensing (inline).
    """
    class VisitTypeChoices(models.TextChoices):
        ILLNESS       = "illness",       "Illness"
        INJURY        = "injury",        "Injury"
        ROUTINE_CHECK = "routine_check", "Routine Check"
        EMERGENCY     = "emergency",     "Emergency"
        FOLLOW_UP     = "follow_up",     "Follow-Up Visit"
    class ActionChoices(models.TextChoices):
        RETURNED_TO_CLASS    = "returned_to_class",    "Returned to Class"
        SENT_HOME            = "sent_home",             "Sent Home"
        REFERRED_HOSPITAL    = "referred_hospital",     "Referred to Hospital"
        OBSERVATION          = "observation",           "Kept Under Observation"
        REFERRED_COUNSELLOR  = "referred_counsellor",  "Referred to Counsellor"
        OTHER                = "other",                 "Other"
    student              = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE,
        related_name="nurse_visits"
    )
    visit_datetime       = models.DateTimeField(default=timezone.now)
    visit_type           = models.CharField(
        max_length=15, choices=VisitTypeChoices.choices,
        default=VisitTypeChoices.ILLNESS
    )
    complaint            = models.TextField(help_text="Student-reported reason for visit")
    temperature_celsius  = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        help_text="Body temperature in °C — flag if >37.5"
    )
    weight_kg            = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    blood_pressure       = models.CharField(
        max_length=20, blank=True,
        help_text="e.g. 120/80 mmHg"
    )
    symptoms             = models.TextField(blank=True, help_text="Nurse-observed symptoms")
    assessment           = models.TextField(blank=True, help_text="Nurse clinical assessment / diagnosis")
    action_taken         = models.CharField(
        max_length=22, choices=ActionChoices.choices,
        default=ActionChoices.RETURNED_TO_CLASS
    )
    parent_notified      = models.BooleanField(default=False)
    parent_notified_time = models.DateTimeField(
        null=True, blank=True,
        help_text="Auto-set when parent_notified is first ticked"
    )
    attended_by          = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="nurse_visits_attended",
        help_text="Nurse or staff member who attended the student"
    )
    follow_up_required   = models.BooleanField(default=False)
    follow_up_date       = models.DateField(null=True, blank=True)
    notes                = models.TextField(blank=True)
    objects = TenantManager()
    class Meta:
        db_table     = "health_nurse_visit"
        ordering     = ["-visit_datetime"]
        verbose_name = "Nurse Visit"
    def __str__(self):
        return (f"{self.student} — {self.get_visit_type_display()} "
                f"({self.visit_datetime:%Y-%m-%d %H:%M})")
    def save(self, *args, **kwargs):
        # Auto-stamp the parent notification time on first tick
        if self.parent_notified and not self.parent_notified_time:
            self.parent_notified_time = timezone.now()
        super().save(*args, **kwargs)
# ══════════════════════════════════════════════════════
# MEDICATION DISPENSING
# ══════════════════════════════════════════════════════
class MedicationDispensing(TenantModel):
    """
    Medications dispensed during a NurseVisit — kept as a separate child record
    so multiple medications per visit are logged individually.
    Mirrors the Infinite Campus medication dispensing log pattern.
    """
    nurse_visit        = models.ForeignKey(
        NurseVisit, on_delete=models.CASCADE,
        related_name="medications_dispensed"
    )
    medication_name    = models.CharField(max_length=150)
    dosage             = models.CharField(max_length=100, help_text="e.g. 500 mg, 2 tablets")
    quantity_dispensed = models.CharField(max_length=50, help_text="e.g. 2 tablets, 5 ml")
    time_dispensed     = models.DateTimeField(default=timezone.now)
    dispensed_by       = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="medications_dispensed_by"
    )
    from_school_stock  = models.BooleanField(
        default=True,
        help_text="True = dispensed from school medical store; False = from student-provided supply"
    )
    notes              = models.CharField(max_length=255, blank=True)
    objects = TenantManager()
    class Meta:
        db_table     = "health_medication_dispensing"
        ordering     = ["time_dispensed"]
        verbose_name = "Medication Dispensing Record"
    def __str__(self):
        return (f"{self.medication_name} {self.dosage} → "
                f"{self.nurse_visit.student} ({self.time_dispensed:%Y-%m-%d %H:%M})")
# ══════════════════════════════════════════════════════
# VACCINATION RECORDS
# ══════════════════════════════════════════════════════
class VaccinationRecord(TenantModel):
    """
    Immunisation history per student — supports multi-dose vaccines.
    administered_by is free-text (external clinic, government campaign)
    rather than a FK to accounts.User because vaccinations are typically
    given by outside health workers, not school staff.
    """
    student          = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE,
        related_name="vaccination_records"
    )
    vaccine_name     = models.CharField(
        max_length=150,
        help_text="e.g. COVID-19, BCG, MMR, Polio, HPV, Hepatitis B"
    )
    vaccination_date  = models.DateField()
    dose_number       = models.PositiveSmallIntegerField(
        default=1,
        help_text="1 = first dose, 2 = second dose, 3 = booster, etc."
    )
    administered_by   = models.CharField(
        max_length=200, blank=True,
        help_text="Clinic name, health worker, or government campaign — not a system user"
    )
    batch_number      = models.CharField(max_length=100, blank=True)
    next_due_date     = models.DateField(
        null=True, blank=True,
        help_text="Date next dose or booster is due — surfaces as alert on health dashboard"
    )
    recorded_by       = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="vaccination_records_entered",
        help_text="School staff who entered this record into the system"
    )
    notes             = models.TextField(blank=True)
    objects = TenantManager()
    class Meta:
        db_table     = "health_vaccination_record"
        ordering     = ["vaccine_name", "dose_number"]
        verbose_name = "Vaccination Record"
    def __str__(self):
        return (f"{self.vaccine_name} dose {self.dose_number} — "
                f"{self.student} ({self.vaccination_date})")

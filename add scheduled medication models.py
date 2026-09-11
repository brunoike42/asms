"""
Patch: adds ScheduledMedication and MedicationAdministrationRecord to the
health app — the eMAR (electronic Medication Administration Record) layer,
benchmarked against Magnus Health. MedicationDispensing (ad-hoc doses given
during a walk-in NurseVisit) is untouched and stays exactly as it is.

Run from the project root (same folder as manage.py):
    python add_scheduled_medication_models.py

Then:
    python -m py_compile apps/health/models.py apps/health/admin.py
    python manage.py makemigrations health
    python manage.py migrate
"""
import pathlib

MODELS_PATH = pathlib.Path("apps/health/models.py")
ADMIN_PATH = pathlib.Path("apps/health/admin.py")

models_text = MODELS_PATH.read_text(encoding="utf-8")
admin_text = ADMIN_PATH.read_text(encoding="utf-8")

MODELS_ANCHOR = '''    def __str__(self):
        return (f"{self.vaccine_name} dose {self.dose_number} — "
                f"{self.student} ({self.vaccination_date})")'''

ADMIN_IMPORT_OLD = "from .models import StudentHealthRecord, NurseVisit, MedicationDispensing, VaccinationRecord"

ADMIN_ANCHOR = '''    search_fields  = ("student__first_name", "student__last_name", "vaccine_name")
    date_hierarchy = "vaccination_date"'''

# ── Validate everything before writing anything ──────────────────────────
assert MODELS_ANCHOR in models_text, (
    "models.py anchor not found — VaccinationRecord.__str__ has changed "
    "since this script was written. Stop and check apps/health/models.py "
    "manually before patching."
)
assert "class ScheduledMedication" not in models_text, (
    "ScheduledMedication already exists in apps/health/models.py — "
    "aborting to avoid a duplicate class."
)
assert ADMIN_IMPORT_OLD in admin_text, (
    "admin.py import line not found — check the .models import in "
    "apps/health/admin.py manually before patching."
)
assert ADMIN_ANCHOR in admin_text, (
    "admin.py anchor not found — VaccinationRecordAdmin has changed. "
    "Stop and check apps/health/admin.py manually before patching."
)
assert "ScheduledMedicationAdmin" not in admin_text, (
    "ScheduledMedicationAdmin already exists in apps/health/admin.py — "
    "aborting to avoid a duplicate registration."
)

NEW_MODELS = '''


# ══════════════════════════════════════════════════════
# SCHEDULED MEDICATION — eMAR (electronic Medication
# Administration Record), benchmarked against Magnus Health
# ══════════════════════════════════════════════════════
class ScheduledMedication(TenantModel):
    """
    An ongoing/recurring medication order for a student — the "prescription"
    side of the eMAR. Separate from MedicationDispensing, which logs a
    one-off dose given during a walk-in NurseVisit. Individual dose
    occurrences for a ScheduledMedication are tracked in
    MedicationAdministrationRecord below.
    """
    class RouteChoices(models.TextChoices):
        ORAL      = "oral",      "Oral"
        TOPICAL   = "topical",   "Topical"
        INHALED   = "inhaled",   "Inhaled"
        INJECTION = "injection", "Injection"
        OTHER     = "other",     "Other"

    class FrequencyChoices(models.TextChoices):
        ONCE_DAILY   = "once_daily",   "Once Daily"
        TWICE_DAILY  = "twice_daily",  "Twice Daily"
        THRICE_DAILY = "thrice_daily", "Three Times Daily"
        AS_NEEDED    = "as_needed",    "As Needed (PRN)"
        OTHER        = "other",        "Other"

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE,
        related_name="scheduled_medications"
    )
    medication_name = models.CharField(max_length=150)
    dosage          = models.CharField(max_length=100, help_text="e.g. 500 mg, 2 tablets")
    route           = models.CharField(
        max_length=10, choices=RouteChoices.choices, default=RouteChoices.ORAL
    )
    frequency       = models.CharField(
        max_length=15, choices=FrequencyChoices.choices, default=FrequencyChoices.ONCE_DAILY
    )
    scheduled_times = models.CharField(
        max_length=150, blank=True,
        help_text="Specific times, e.g. '8:00 AM, 2:00 PM' — informs when pending doses are generated"
    )
    start_date = models.DateField(help_text="Date this medication order begins")
    end_date   = models.DateField(
        null=True, blank=True,
        help_text="Leave blank for an ongoing / indefinite order"
    )
    is_active  = models.BooleanField(default=True)
    authorization_notes = models.TextField(
        blank=True,
        help_text="Parent/doctor authorization details — formal consent capture "
                   "lives in apps.parent_portal.ConsentForm, not duplicated here"
    )
    prescribing_doctor = models.CharField(max_length=150, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scheduled_medications_created"
    )
    notes = models.TextField(blank=True)
    objects = TenantManager()

    class Meta:
        db_table     = "health_scheduled_medication"
        ordering     = ["-is_active", "student__last_name"]
        verbose_name = "Scheduled Medication"

    def __str__(self):
        return f"{self.medication_name} ({self.get_frequency_display()}) — {self.student}"


class MedicationAdministrationRecord(TenantModel):
    """
    One record per scheduled dose occurrence — the actual eMAR entry.
    How PENDING rows get generated (view-time, management command, or
    Celery Beat) is a decision for the views layer, not this model.
    """
    class StatusChoices(models.TextChoices):
        PENDING      = "pending",      "Pending"
        ADMINISTERED = "administered", "Administered"
        REFUSED      = "refused",      "Refused"

    scheduled_medication = models.ForeignKey(
        ScheduledMedication, on_delete=models.CASCADE,
        related_name="administration_records"
    )
    scheduled_datetime = models.DateTimeField(help_text="When this dose was due")
    status = models.CharField(
        max_length=15, choices=StatusChoices.choices, default=StatusChoices.PENDING
    )
    administered_time = models.DateTimeField(null=True, blank=True)
    administered_by   = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="medications_administered"
    )
    refusal_reason = models.CharField(
        max_length=255, blank=True,
        help_text="Context for a Refused status"
    )
    notes = models.CharField(max_length=255, blank=True)
    objects = TenantManager()

    class Meta:
        db_table     = "health_medication_administration_record"
        ordering     = ["scheduled_datetime"]
        verbose_name = "Medication Administration Record"

    def __str__(self):
        return (f"{self.scheduled_medication.medication_name} — "
                f"{self.get_status_display()} ({self.scheduled_datetime:%Y-%m-%d %H:%M})")

    def save(self, *args, **kwargs):
        # Mirrors NurseVisit's auto-stamp pattern
        if self.status == self.StatusChoices.ADMINISTERED and not self.administered_time:
            self.administered_time = timezone.now()
        super().save(*args, **kwargs)
'''

ADMIN_IMPORT_NEW = (
    "from .models import StudentHealthRecord, NurseVisit, MedicationDispensing, "
    "VaccinationRecord, ScheduledMedication, MedicationAdministrationRecord"
)

NEW_ADMIN = '''


@admin.register(ScheduledMedication)
class ScheduledMedicationAdmin(admin.ModelAdmin):
    list_display   = ("student", "medication_name", "frequency", "is_active", "start_date", "end_date")
    list_filter    = ("frequency", "route", "is_active")
    search_fields  = ("student__first_name", "student__last_name", "medication_name")
    date_hierarchy = "start_date"


@admin.register(MedicationAdministrationRecord)
class MedicationAdministrationRecordAdmin(admin.ModelAdmin):
    list_display   = ("scheduled_medication", "status", "scheduled_datetime", "administered_by")
    list_filter    = ("status",)
    search_fields  = (
        "scheduled_medication__student__first_name",
        "scheduled_medication__student__last_name",
        "scheduled_medication__medication_name",
    )
    date_hierarchy = "scheduled_datetime"
'''

# ── Write both, now that both are validated ──────────────────────────────
MODELS_PATH.write_text(models_text.replace(MODELS_ANCHOR, MODELS_ANCHOR + NEW_MODELS, 1), encoding="utf-8")

admin_text = admin_text.replace(ADMIN_IMPORT_OLD, ADMIN_IMPORT_NEW, 1)
admin_text = admin_text.replace(ADMIN_ANCHOR, ADMIN_ANCHOR + NEW_ADMIN, 1)
ADMIN_PATH.write_text(admin_text, encoding="utf-8")

print("Patched apps/health/models.py — added ScheduledMedication, MedicationAdministrationRecord")
print("Patched apps/health/admin.py — registered both in Django admin")
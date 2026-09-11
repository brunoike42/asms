from django.contrib import admin
from .models import StudentHealthRecord, NurseVisit, MedicationDispensing, VaccinationRecord
@admin.register(StudentHealthRecord)
class StudentHealthRecordAdmin(admin.ModelAdmin):
    list_display    = ("student", "blood_type", "is_on_regular_medication", "has_critical_alerts")
    list_filter     = ("blood_type", "is_on_regular_medication")
    search_fields   = ("student__first_name", "student__last_name", "student__student_id")
    readonly_fields = ("last_updated_by",)
    fieldsets = (
        ("Student",          {"fields": ("tenant", "student")}),
        ("Medical Profile",  {"fields": (
            "blood_type", "allergies", "chronic_conditions", "physical_disabilities",
            "is_on_regular_medication", "regular_medication_details",
            "special_dietary_requirements",
        )}),
        ("Emergency Contacts", {"fields": (
            "emergency_contact_1_name", "emergency_contact_1_phone", "emergency_contact_1_relationship",
            "emergency_contact_2_name", "emergency_contact_2_phone", "emergency_contact_2_relationship",
        )}),
        ("Medical Provider", {"fields": (
            "doctor_name", "doctor_phone", "hospital_preference",
            "medical_insurance_provider", "medical_insurance_number",
        )}),
        ("Notes",            {"fields": ("notes", "last_updated_by")}),
    )
    def has_critical_alerts(self, obj):
        return obj.has_critical_alerts
    has_critical_alerts.boolean = True
    has_critical_alerts.short_description = "Alerts"
class MedicationDispensingInline(admin.TabularInline):
    model          = MedicationDispensing
    extra          = 1
    readonly_fields = ("time_dispensed",)
@admin.register(NurseVisit)
class NurseVisitAdmin(admin.ModelAdmin):
    list_display    = ("student", "visit_type", "visit_datetime", "action_taken",
                       "parent_notified", "follow_up_required")
    list_filter     = ("visit_type", "action_taken", "parent_notified", "follow_up_required")
    search_fields   = ("student__first_name", "student__last_name", "complaint")
    date_hierarchy  = "visit_datetime"
    readonly_fields = ("parent_notified_time",)
    inlines         = [MedicationDispensingInline]
@admin.register(VaccinationRecord)
class VaccinationRecordAdmin(admin.ModelAdmin):
    list_display   = ("student", "vaccine_name", "dose_number", "vaccination_date",
                      "next_due_date", "administered_by")
    list_filter    = ("vaccine_name",)
    search_fields  = ("student__first_name", "student__last_name", "vaccine_name")
    date_hierarchy = "vaccination_date"

from django.contrib import admin
from .models import SchoolInfrastructureRecord, EMISSubmission
@admin.register(SchoolInfrastructureRecord)
class SchoolInfrastructureRecordAdmin(admin.ModelAdmin):
    list_display  = ("academic_year", "total_classrooms", "functional_classrooms",
                     "has_electricity", "has_internet", "computer_count")
    list_filter   = ("has_electricity", "has_internet", "has_laboratory", "has_computer_lab")
    fieldsets = (
        ("Year",        {"fields": ("tenant", "academic_year")}),
        ("Classrooms",  {"fields": ("total_classrooms", "functional_classrooms")}),
        ("Utilities",   {"fields": ("has_electricity", "has_piped_water", "has_borehole",
                                    "has_internet", "internet_type")}),
        ("Sanitation",  {"fields": ("toilet_blocks_boys", "toilet_blocks_girls",
                                    "toilet_blocks_teachers")}),
        ("Facilities",  {"fields": ("has_library", "library_books",
                                    "has_laboratory", "lab_count",
                                    "has_computer_lab", "computer_count",
                                    "has_sports_field")}),
        ("Notes",       {"fields": ("notes", "last_updated_by")}),
    )
@admin.register(EMISSubmission)
class EMISSubmissionAdmin(admin.ModelAdmin):
    list_display  = ("academic_year", "country_template", "generated_at", "status",
                     "compliance_issue_count", "submission_reference")
    list_filter   = ("status", "country_template", "academic_year")
    readonly_fields = ("generated_at", "compliance_issues", "compliance_issue_count")
    def compliance_issue_count(self, obj):
        count = obj.compliance_issue_count
        return f"{count} issue(s)" if count else "Clean"
    compliance_issue_count.short_description = "Compliance"

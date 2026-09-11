
from django.contrib import admin
from .models import StaffProfile, LeaveType, LeaveRequest, CPDRecord

@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'designation', 'department', 'employment_type', 'is_active', 'tenant']
    list_filter = ['employment_type', 'is_active', 'tenant']

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['staff', 'leave_type', 'start_date', 'end_date', 'status', 'tenant']
    list_filter = ['status', 'tenant']

admin.site.register(LeaveType)
admin.site.register(CPDRecord)
# ── Staff PD admin (Phase 4 additions) ───────────────
from django.contrib import admin as _admin
from .models import StaffAppraisal, AppraisalObjective, TrainingPlan, TrainingPlanItem
class AppraisalObjectiveInline(_admin.TabularInline):
    model   = AppraisalObjective
    extra   = 1
@_admin.register(StaffAppraisal)
class StaffAppraisalAdmin(_admin.ModelAdmin):
    list_display  = ("staff_member", "appraisal_period", "appraisal_date",
                     "average_score", "status")
    list_filter   = ("status", "academic_year")
    search_fields = ("staff_member__first_name", "staff_member__last_name",
                     "appraisal_period")
    inlines       = [AppraisalObjectiveInline]
    def average_score(self, obj):
        return obj.average_score
    average_score.short_description = "Avg Score"
class TrainingPlanItemInline(_admin.TabularInline):
    model = TrainingPlanItem
    extra = 1
@_admin.register(TrainingPlan)
class TrainingPlanAdmin(_admin.ModelAdmin):
    list_display  = ("staff_member", "academic_year", "status", "completion_rate")
    list_filter   = ("status", "academic_year")
    search_fields = ("staff_member__first_name", "staff_member__last_name")
    inlines       = [TrainingPlanItemInline]
    def completion_rate(self, obj):
        return f"{obj.completion_rate}%"
    completion_rate.short_description = "Complete"

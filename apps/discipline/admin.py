from django.contrib import admin
from .models import (
    DisciplineCategory, DisciplineIncident, DisciplineConsequence,
    IncidentWitness, IncidentEvidence, MeritRecord, StudentBehaviourSummary
)


@admin.register(DisciplineCategory)
class DisciplineCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'default_severity', 'requires_principal_approval', 'triggers_counselling', 'is_active', 'tenant')
    list_filter = ('default_severity', 'requires_principal_approval', 'is_active', 'tenant')
    search_fields = ('name', 'code')


class DisciplineConsequenceInline(admin.TabularInline):
    model = DisciplineConsequence
    extra = 0
    fields = ('consequence_type', 'description', 'approval_status', 'assigned_by')
    readonly_fields = ('assigned_by', 'assigned_at')


class IncidentWitnessInline(admin.TabularInline):
    model = IncidentWitness
    extra = 0
    fields = ('witness_type', 'witness_name', 'statement')


@admin.register(DisciplineIncident)
class DisciplineIncidentAdmin(admin.ModelAdmin):
    list_display = (
        'reference_number', 'student', 'category', 'severity',
        'status', 'incident_date', 'parent_notified', 'tenant'
    )
    list_filter = ('severity', 'status', 'category', 'tenant', 'incident_date')
    search_fields = ('reference_number', 'student__first_name', 'student__last_name', 'title')
    readonly_fields = ('reference_number', 'report_datetime', 'created_at', 'updated_at')
    inlines = [DisciplineConsequenceInline, IncidentWitnessInline]
    date_hierarchy = 'incident_date'


@admin.register(DisciplineConsequence)
class DisciplineConsequenceAdmin(admin.ModelAdmin):
    list_display = ('incident', 'consequence_type', 'approval_status', 'assigned_by', 'assigned_at')
    list_filter = ('consequence_type', 'approval_status')


@admin.register(MeritRecord)
class MeritRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'merit_type', 'title', 'merit_points', 'award_date', 'awarded_by', 'tenant')
    list_filter = ('merit_type', 'tenant', 'term')
    search_fields = ('student__first_name', 'student__last_name', 'title')


@admin.register(StudentBehaviourSummary)
class StudentBehaviourSummaryAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'term', 'total_incidents', 'total_demerit_points',
        'total_merit_points', 'counselling_flag_raised', 'last_computed_at'
    )
    list_filter = ('term', 'counselling_flag_raised')
    readonly_fields = ('last_computed_at',)

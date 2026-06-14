from django.contrib import admin
from .models import (
    WelfareCase, CounsellingSession, WelfareCaseAction,
    BursaryApplication, CounsellorReferral, AtRiskRegister
)


class CounsellingSessionInline(admin.TabularInline):
    model = CounsellingSession
    extra = 0
    fields = ('session_date', 'session_type', 'student_attended', 'urgency_level', 'conducted_by')
    readonly_fields = ('conducted_by',)


class WelfareCaseActionInline(admin.TabularInline):
    model = WelfareCaseAction
    extra = 0
    fields = ('action_type', 'description', 'action_date', 'outcome', 'completed_by')
    readonly_fields = ('completed_by',)


@admin.register(WelfareCase)
class WelfareCaseAdmin(admin.ModelAdmin):
    list_display = (
        'reference_number', 'student', 'case_type', 'priority',
        'status', 'assigned_counsellor', 'days_open',
        'involves_safeguarding', 'auto_opened', 'tenant'
    )
    list_filter = (
        'status', 'priority', 'case_type', 'trigger',
        'involves_safeguarding', 'auto_opened', 'tenant'
    )
    search_fields = (
        'reference_number', 'student__first_name', 'student__last_name', 'title'
    )
    readonly_fields = ('reference_number', 'created_at', 'updated_at')
    inlines = [CounsellingSessionInline, WelfareCaseActionInline]
    date_hierarchy = 'created_at'
    fieldsets = (
        ('Core', {
            'fields': ('reference_number', 'tenant', 'student', 'case_type',
                       'title', 'description', 'priority', 'status', 'trigger', 'auto_opened')
        }),
        ('Assignment', {
            'fields': ('opened_by', 'assigned_counsellor', 'assigned_at')
        }),
        ('Risk Snapshot', {
            'fields': ('risk_score_at_opening', 'risk_signals_at_opening')
        }),
        ('Safeguarding', {
            'fields': ('involves_safeguarding', 'involves_abuse', 'involves_self_harm_risk'),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': ('resolved_at', 'resolved_by', 'resolution_summary', 'outcome'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CounsellingSession)
class CounsellingSessionAdmin(admin.ModelAdmin):
    list_display = (
        'welfare_case', 'session_date', 'session_type',
        'student_attended', 'urgency_level', 'safeguarding_concern_raised', 'conducted_by'
    )
    list_filter = ('session_type', 'urgency_level', 'safeguarding_concern_raised', 'student_attended')
    search_fields = ('welfare_case__reference_number', 'welfare_case__student__first_name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'session_date'


@admin.register(BursaryApplication)
class BursaryApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'waiver_type', 'amount_requested',
        'status', 'submitted_by', 'amount_approved', 'tenant'
    )
    list_filter = ('status', 'waiver_type', 'tenant')
    search_fields = ('student__first_name', 'student__last_name')
    readonly_fields = ('created_at', 'updated_at', 'submitted_at', 'approved_at')


@admin.register(CounsellorReferral)
class CounsellorReferralAdmin(admin.ModelAdmin):
    list_display = (
        'welfare_case', 'referral_type', 'referred_to_name',
        'referral_date', 'status', 'made_by'
    )
    list_filter = ('referral_type', 'status')
    search_fields = ('referred_to_name', 'welfare_case__reference_number')


@admin.register(AtRiskRegister)
class AtRiskRegisterAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'risk_score', 'risk_level',
        'attendance_score', 'academic_score', 'behaviour_score',
        'counsellor_actioned', 'computed_at', 'tenant'
    )
    list_filter = ('risk_level', 'counsellor_actioned', 'tenant')
    search_fields = ('student__first_name', 'student__last_name')
    readonly_fields = ('computed_at',)
    ordering = ('-risk_score',)

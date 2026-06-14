"""
ASMS — Student Portal Admin
All portal models registered with the Django admin.
"""
from django.contrib import admin
from .models import (
    TermEnrollment,
    CourseUnitRegistration,
    ExamPermit,
    ExamAppeal,
    ProgramChangeRequest,
    LeaveOfAbsenceRequest,
    AcademicClearanceItem,
    StudentClearance,
    StudentClearanceItemStatus,
    AcademicCalendarEvent,
    PortalNotification,
)


# ─── Inline classes ────────────────────────────────────────────────────────
class CourseUnitRegistrationInline(admin.TabularInline):
    model  = CourseUnitRegistration
    extra  = 0
    fields = ('subject', 'paper_type', 'is_active', 'registered_at')
    readonly_fields = ('registered_at',)


class StudentClearanceItemStatusInline(admin.TabularInline):
    model  = StudentClearanceItemStatus
    extra  = 0
    fields = ('item', 'status', 'cleared_by', 'cleared_at', 'remarks')
    readonly_fields = ('cleared_at',)


# ─── Model admins ──────────────────────────────────────────────────────────
@admin.register(TermEnrollment)
class TermEnrollmentAdmin(admin.ModelAdmin):
    list_display   = ('student', 'term', 'status', 'study_year', 'is_confirmed', 'confirmed_at')
    list_filter    = ('status', 'is_confirmed', 'term')
    search_fields  = ('student__user__first_name', 'student__user__last_name', 'student__student_id')
    raw_id_fields  = ('student', 'term')
    readonly_fields = ('enrolled_at', 'confirmed_at')
    inlines        = [CourseUnitRegistrationInline]
    actions        = ['confirm_selected']

    @admin.action(description='Confirm selected enrollments')
    def confirm_selected(self, request, queryset):
        for enr in queryset.filter(is_confirmed=False):
            enr.confirm()
        self.message_user(request, f"{queryset.count()} enrollment(s) confirmed.")


@admin.register(ExamPermit)
class ExamPermitAdmin(admin.ModelAdmin):
    list_display  = ('permit_number', 'enrollment', 'status', 'issued_at')
    list_filter   = ('status',)
    search_fields = ('permit_number', 'enrollment__student__student_id')
    readonly_fields = ('issued_at',)
    actions       = ['issue_selected', 'block_selected']

    @admin.action(description='Issue selected permits')
    def issue_selected(self, request, queryset):
        for permit in queryset.filter(status='pending'):
            permit.issue()

    @admin.action(description='Block selected permits')
    def block_selected(self, request, queryset):
        queryset.update(status='blocked', blocked_reason='Blocked by administrator.')


@admin.register(ExamAppeal)
class ExamAppealAdmin(admin.ModelAdmin):
    list_display  = ('reference_number', 'student', 'subject', 'term',
                     'appeal_type', 'status', 'submitted_at')
    list_filter   = ('status', 'appeal_type', 'term')
    search_fields = ('reference_number', 'student__user__first_name',
                     'student__user__last_name', 'student__student_id')
    raw_id_fields = ('student', 'subject', 'term', 'resolved_by')
    readonly_fields = ('submitted_at', 'resolved_at', 'reference_number')
    fieldsets = (
        ('Appeal Details', {
            'fields': ('tenant', 'student', 'term', 'subject',
                       'appeal_type', 'original_marks', 'statement',
                       'reference_number', 'submitted_at')
        }),
        ('Resolution', {
            'fields': ('status', 'admin_response', 'revised_marks',
                       'resolved_by', 'resolved_at')
        }),
    )


@admin.register(ProgramChangeRequest)
class ProgramChangeRequestAdmin(admin.ModelAdmin):
    list_display  = ('student', 'current_class', 'requested_class', 'status', 'submitted_at')
    list_filter   = ('status',)
    search_fields = ('student__user__first_name', 'student__user__last_name', 'student__student_id')
    readonly_fields = ('submitted_at', 'reviewed_at')


@admin.register(LeaveOfAbsenceRequest)
class LeaveOfAbsenceRequestAdmin(admin.ModelAdmin):
    list_display  = ('student', 'leave_type', 'from_term', 'status', 'submitted_at')
    list_filter   = ('status', 'leave_type')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'student__student_id')
    readonly_fields = ('submitted_at', 'reviewed_at')


@admin.register(AcademicClearanceItem)
class AcademicClearanceItemAdmin(admin.ModelAdmin):
    list_display  = ('name', 'department', 'is_active', 'order')
    list_filter   = ('department', 'is_active')
    list_editable = ('is_active', 'order')
    ordering      = ('order',)


@admin.register(StudentClearance)
class StudentClearanceAdmin(admin.ModelAdmin):
    list_display   = ('student', 'academic_year', 'overall_status', 'requested_at')
    list_filter    = ('overall_status',)
    search_fields  = ('student__user__first_name', 'student__user__last_name', 'student__student_id')
    readonly_fields = ('requested_at', 'cleared_at')
    inlines        = [StudentClearanceItemStatusInline]


@admin.register(AcademicCalendarEvent)
class AcademicCalendarEventAdmin(admin.ModelAdmin):
    list_display   = ('title', 'event_type', 'start_date', 'end_date', 'audience', 'is_published')
    list_filter    = ('event_type', 'audience', 'is_published', 'academic_year')
    list_editable  = ('is_published',)
    search_fields  = ('title', 'description')
    date_hierarchy = 'start_date'
    fieldsets = (
        ('Event Details', {
            'fields': ('tenant', 'title', 'event_type', 'description',
                       'start_date', 'end_date', 'audience', 'is_published')
        }),
        ('Scope', {
            'fields': ('academic_year', 'term', 'created_by')
        }),
    )


@admin.register(PortalNotification)
class PortalNotificationAdmin(admin.ModelAdmin):
    list_display   = ('title', 'student', 'category', 'is_read', 'created_at')
    list_filter    = ('category', 'is_read')
    search_fields  = ('title', 'student__user__first_name', 'student__user__last_name')
    readonly_fields = ('created_at', 'read_at')
    date_hierarchy = 'created_at'

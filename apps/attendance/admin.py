from django.contrib import admin
from .models import AttendanceRecord, AttendanceSummary

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display  = ['student', 'date', 'status', 'classroom', 'marked_by', 'parent_notified']
    list_filter   = ['status', 'date', 'tenant', 'parent_notified']
    search_fields = ['student__first_name', 'student__last_name']
    date_hierarchy = 'date'

@admin.register(AttendanceSummary)
class AttendanceSummaryAdmin(admin.ModelAdmin):
    list_display  = ['student', 'term', 'attendance_pct', 'days_absent', 'consecutive_absences']
    list_filter   = ['term', 'tenant']

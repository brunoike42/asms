from django.contrib import admin
from .models import AttendanceRecord, AttendanceSummary
from .models import BiometricDevice, BiometricTemplate, BiometricScanLog


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






@admin.register(BiometricDevice)
class BiometricDeviceAdmin(admin.ModelAdmin):
    list_display = ['name', 'device_type', 'serial_number', 'location',
                     'classroom', 'status', 'last_seen_at']
    list_filter = ['device_type', 'status']
    search_fields = ['name', 'serial_number', 'location']
    readonly_fields = ['secret_key', 'last_seen_at', 'created_at']

    def get_readonly_fields(self, request, obj=None):
        # Secret key is generated on first save and should never be edited
        # via admin — regenerate by deleting/recreating the device if compromised.
        return self.readonly_fields


@admin.register(BiometricTemplate)
class BiometricTemplateAdmin(admin.ModelAdmin):
    list_display = ['student', 'device', 'template_id', 'is_active', 'enrolled_at']
    list_filter = ['device', 'is_active']
    search_fields = ['student__first_name', 'student__last_name', 'template_id']


@admin.register(BiometricScanLog)
class BiometricScanLogAdmin(admin.ModelAdmin):
    list_display = ['device', 'student', 'result', 'scanned_at', 'received_at']
    list_filter = ['result', 'device']
    search_fields = ['student__first_name', 'student__last_name']
    readonly_fields = ['device', 'student', 'template_id_raw', 'scanned_at',
                        'received_at', 'result', 'attendance_record', 'raw_payload']
    date_hierarchy = 'received_at'

    def has_add_permission(self, request):
        # This is an audit log — entries are only created by the scan endpoint
        return False

    def has_change_permission(self, request, obj=None):
        return False

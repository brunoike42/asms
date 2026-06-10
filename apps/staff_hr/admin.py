
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

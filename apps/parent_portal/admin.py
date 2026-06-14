from django.contrib import admin
from .models import (
    ParentMeetingBooking, AbsenceExcuse,
    ParentNotification, ActivityPost, ConsentForm, ConsentResponse
)


@admin.register(ParentMeetingBooking)
class ParentMeetingBookingAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'parent_user', 'teacher', 'meeting_type',
        'preferred_date', 'preferred_time', 'status', 'tenant'
    )
    list_filter  = ('status', 'meeting_type', 'tenant')
    search_fields = ('student__first_name', 'student__last_name', 'parent_user__email')
    readonly_fields = ('created_at', 'updated_at', 'confirmed_at', 'completed_at')
    date_hierarchy = 'preferred_date'


@admin.register(AbsenceExcuse)
class AbsenceExcuseAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'parent_user', 'absence_date',
        'excuse_type', 'status', 'reviewed_by', 'tenant'
    )
    list_filter  = ('status', 'excuse_type', 'tenant')
    search_fields = ('student__first_name', 'student__last_name')
    readonly_fields = ('created_at', 'reviewed_at')
    date_hierarchy = 'absence_date'

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data and obj.status in ('approved', 'rejected'):
            obj.reviewed_by = request.user
            from django.utils import timezone
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(ParentNotification)
class ParentNotificationAdmin(admin.ModelAdmin):
    list_display = (
        'parent_user', 'student', 'category', 'title',
        'is_read', 'is_urgent', 'created_at', 'tenant'
    )
    list_filter  = ('category', 'is_read', 'is_urgent', 'tenant')
    search_fields = ('title', 'parent_user__email', 'student__first_name')
    readonly_fields = ('created_at', 'read_at')
    date_hierarchy = 'created_at'
    actions = ['mark_as_read']

    @admin.action(description='Mark selected as read')
    def mark_as_read(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_read=True, read_at=timezone.now())


@admin.register(ActivityPost)
class ActivityPostAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'post_type', 'audience', 'posted_by',
        'classroom', 'is_pinned', 'created_at', 'tenant'
    )
    list_filter  = ('post_type', 'audience', 'is_pinned', 'tenant')
    search_fields = ('title', 'body')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'


class ConsentResponseInline(admin.TabularInline):
    model = ConsentResponse
    extra = 0
    readonly_fields = ('signed_at',)


@admin.register(ConsentForm)
class ConsentFormAdmin(admin.ModelAdmin):
    list_display  = ('title', 'form_type', 'deadline', 'is_active', 'tenant')
    list_filter   = ('form_type', 'is_active', 'tenant')
    search_fields = ('title',)
    readonly_fields = ('created_at',)
    inlines = [ConsentResponseInline]
    filter_horizontal = ('target_classes',)


@admin.register(ConsentResponse)
class ConsentResponseAdmin(admin.ModelAdmin):
    list_display = ('student', 'form', 'consented', 'parent_user', 'signed_at')
    list_filter  = ('consented',)
    readonly_fields = ('signed_at',)

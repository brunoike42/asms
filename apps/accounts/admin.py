from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display   = ['email', 'get_full_name', 'role', 'tenant', 'is_active']
    list_filter    = ['role', 'is_active', 'tenant']
    search_fields  = ['email', 'first_name', 'last_name']
    ordering       = ['last_name', 'first_name']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'photo')}),
        ('Role & Tenant', {'fields': ('role', 'tenant')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'must_change_password')}),
        ('Notifications', {'fields': ('notify_sms', 'notify_email', 'notify_push')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 'tenant', 'password1', 'password2'),
        }),
    )

from django.contrib import admin
from .models import Tenant, AcademicYear, Term


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display  = ['name', 'slug', 'school_type', 'plan', 'status', 'country', 'is_active']
    list_filter   = ['plan', 'status', 'school_type', 'country']
    search_fields = ['name', 'slug', 'emis_code']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display  = ['name', 'tenant', 'start_date', 'end_date', 'is_current']
    list_filter   = ['is_current', 'tenant']


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display  = ['name', 'academic_year', 'start_date', 'end_date', 'is_current']
    list_filter   = ['is_current', 'academic_year__tenant']

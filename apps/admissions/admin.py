from django.contrib import admin
from .models import AdmissionApplication

@admin.register(AdmissionApplication)
class AdmissionApplicationAdmin(admin.ModelAdmin):
    list_display  = ['application_number', 'get_full_name', 'applying_for_level', 'status', 'applied_date', 'tenant']
    list_filter   = ['status', 'tenant', 'applying_for_level']
    search_fields = ['first_name', 'last_name', 'application_number', 'guardian_phone']

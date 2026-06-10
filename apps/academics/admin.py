
from django.contrib import admin
from .models import Subject, ClassSubject, Department, TimetableSlot

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'department', 'is_compulsory', 'tenant']

@admin.register(ClassSubject)
class ClassSubjectAdmin(admin.ModelAdmin):
    list_display = ['classroom', 'subject', 'teacher', 'term', 'tenant']

admin.site.register(Department)
admin.site.register(TimetableSlot)

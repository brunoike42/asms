
from django.contrib import admin
from .models import Assignment, AssignmentSubmission, AssignmentRubric

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'class_subject', 'status', 'due_date', 'max_marks', 'tenant']
    list_filter = ['status', 'tenant']

@admin.register(AssignmentSubmission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['student', 'assignment', 'status', 'marks', 'grade', 'submitted_at']

admin.site.register(AssignmentRubric)


from django.contrib import admin
from .models import Exam, ExamResult, TermReport, SubjectScore

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'exam_type', 'classroom', 'subject', 'term', 'is_published', 'tenant']
    list_filter = ['exam_type', 'is_published', 'tenant']

@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ['student', 'exam', 'score', 'grade', 'tenant']

@admin.register(TermReport)
class TermReportAdmin(admin.ModelAdmin):
    list_display = ['student', 'term', 'classroom', 'average_score', 'position', 'is_published']

admin.site.register(SubjectScore)

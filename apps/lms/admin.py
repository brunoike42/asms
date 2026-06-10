
from django.contrib import admin
from .models import LessonPlan, LMSResource, Quiz, QuizQuestion, QuizOption, QuizAttempt

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'class_subject', 'is_published', 'duration_minutes', 'tenant']

@admin.register(LMSResource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ['title', 'resource_type', 'class_subject', 'is_published', 'tenant']

admin.site.register(LessonPlan)
admin.site.register(QuizQuestion)
admin.site.register(QuizOption)
admin.site.register(QuizAttempt)

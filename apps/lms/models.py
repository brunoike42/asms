from django.db import models
from apps.core.models import Tenant, TenantManager, Term
from apps.academics.models import ClassSubject, Subject
from apps.students.models import ClassRoom
from django.conf import settings

class LessonPlan(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='lesson_plans')
    title = models.CharField(max_length=200)
    week_number = models.IntegerField()
    lesson_number = models.IntegerField(default=1)
    objectives = models.TextField(blank=True)
    content = models.TextField()
    activities = models.TextField(blank=True)
    resources_needed = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    completed_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'lesson_plans'
        ordering = ['week_number', 'lesson_number']

    def __str__(self):
        return f"Week {self.week_number}: {self.title}"

class LMSResource(models.Model):
    RESOURCE_TYPES = [
        ('document', 'Document'), ('video_link', 'Video Link'), ('image', 'Image'),
        ('audio', 'Audio'), ('link', 'External Link'), ('past_paper', 'Past Paper'),
        ('notes', 'Notes'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES, default='document')
    file = models.FileField(upload_to='lms_resources/', blank=True, null=True)
    external_url = models.URLField(blank=True)
    week_number = models.IntegerField(null=True, blank=True)
    is_published = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    download_count = models.IntegerField(default=0)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'lms_resources'
        ordering = ['-upload_date']

    def __str__(self):
        return f"{self.title} ({self.resource_type})"

class Quiz(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    duration_minutes = models.IntegerField(default=30)
    max_attempts = models.IntegerField(default=1)
    is_published = models.BooleanField(default=False)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    shuffle_questions = models.BooleanField(default=False)
    show_results = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'quizzes'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.class_subject}"

    @property
    def question_count(self):
        return self.questions.count()

class QuizQuestion(models.Model):
    QUESTION_TYPES = [
        ('mcq', 'Multiple Choice'), ('true_false', 'True/False'), ('short_answer', 'Short Answer'),
    ]
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='mcq')
    marks = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    order = models.IntegerField(default=0)
    explanation = models.TextField(blank=True, help_text='Shown after submission')

    class Meta:
        db_table = 'quiz_questions'
        ordering = ['order']

class QuizOption(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    class Meta:
        db_table = 'quiz_options'

class QuizAttempt(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='quiz_attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_complete = models.BooleanField(default=False)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'quiz_attempts'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.student} — {self.quiz.title} ({self.score})"

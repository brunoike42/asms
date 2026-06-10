from django.db import models
from django.conf import settings
from apps.core.models import Tenant, TenantManager
from apps.academics.models import ClassSubject
from apps.students.models import Student

class Assignment(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'), ('published', 'Published'), ('closed', 'Closed'), ('graded', 'Graded'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=200)
    description = models.TextField()
    instructions = models.TextField(blank=True)
    max_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    due_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    allow_late = models.BooleanField(default=False)
    allow_resubmit = models.BooleanField(default=False)
    attachment = models.FileField(upload_to='assignment_attachments/', blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'assignments'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.class_subject}"

    @property
    def is_overdue(self):
        from django.utils import timezone
        return timezone.now() > self.due_date

    @property
    def submission_count(self):
        return self.submissions.count()

class AssignmentSubmission(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Submitted'), ('late', 'Late'), ('graded', 'Graded'), ('returned', 'Returned'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='submissions')
    content = models.TextField(blank=True, help_text='Written submission')
    file = models.FileField(upload_to='submission_files/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    submitted_at = models.DateTimeField(auto_now_add=True)
    marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    grade = models.CharField(max_length=5, blank=True)
    teacher_comment = models.TextField(blank=True)
    annotated_file = models.FileField(upload_to='annotated_submissions/', blank=True, null=True)
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='graded_submissions')
    graded_at = models.DateTimeField(null=True, blank=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'assignment_submissions'
        unique_together = ['assignment', 'student']
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.student} — {self.assignment.title}"

class AssignmentRubric(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='rubrics')
    criterion = models.CharField(max_length=200)
    max_marks = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'assignment_rubrics'

    def __str__(self):
        return f"{self.criterion} ({self.max_marks} marks)"

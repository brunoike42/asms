from django.db import models
from apps.core.models import Tenant, TenantManager, Term
from apps.students.models import Student, ClassRoom
from apps.academics.models import Subject
from django.conf import settings


GRADE_BOUNDARIES = [
    (90, 'A'), (80, 'B'), (70, 'C'), (60, 'D'), (50, 'E'), (0, 'F')
]

def compute_grade(score, max_score=100):
    pct = (score / max_score) * 100 if max_score else 0
    for boundary, grade in GRADE_BOUNDARIES:
        if pct >= boundary:
            return grade
    return 'F'

class Exam(models.Model):
    TYPE_CHOICES = [
        ('ca1', 'CA 1'), ('ca2', 'CA 2'), ('ca3', 'CA 3'),
        ('mid_term', 'Mid-Term'), ('end_term', 'End of Term'),
        ('mock', 'Mock Exam'), ('national', 'National Exam'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    exam_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='exams')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='exams')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    exam_date = models.DateField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'exams'
        ordering = ['-exam_date']

    def __str__(self):
        return f"{self.name} — {self.classroom} ({self.term})"

class ExamResult(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='results')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exam_results')
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    grade = models.CharField(max_length=5, blank=True)
    remarks = models.CharField(max_length=200, blank=True)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    entered_at = models.DateTimeField(auto_now_add=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'exam_results'
        unique_together = ['exam', 'student']

    def save(self, *args, **kwargs):
        if self.score is not None:
            self.grade = compute_grade(float(self.score), float(self.exam.max_score))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} — {self.exam.name}: {self.score}/{self.exam.max_score}"

class TermReport(models.Model):
    """Aggregated end-of-term report for one student."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='term_reports')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='reports')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE)
    total_marks = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    average_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    position = models.IntegerField(null=True, blank=True)
    out_of = models.IntegerField(null=True, blank=True)
    class_teacher_comment = models.TextField(blank=True)
    principal_comment = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    computed_at = models.DateTimeField(auto_now=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'term_reports'
        unique_together = ['student', 'term']
        ordering = ['position']

    def __str__(self):
        return f"{self.student} — {self.term} Report (Pos: {self.position})"

class SubjectScore(models.Model):
    """Per-subject aggregate score on a TermReport."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    report = models.ForeignKey(TermReport, on_delete=models.CASCADE, related_name='subject_scores')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    total_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    max_possible = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    grade = models.CharField(max_length=5, blank=True)
    teacher_comment = models.CharField(max_length=200, blank=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'subject_scores'
        unique_together = ['report', 'subject']

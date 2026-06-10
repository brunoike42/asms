from django.db import models
from apps.core.models import Tenant, TenantManager, Term, AcademicYear
from apps.students.models import ClassRoom
from django.conf import settings

class Department(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    head = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'departments'

    def __str__(self):
        return self.name

class Subject(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    is_compulsory = models.BooleanField(default=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'subjects'
        ordering = ['name']

    def __str__(self):
        return self.name

class ClassSubject(models.Model):
    """Links a subject to a class with a specific teacher for a term."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='class_subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    periods_per_week = models.IntegerField(default=4)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'class_subjects'
        unique_together = ['classroom', 'subject', 'term']

    def __str__(self):
        return f"{self.classroom} — {self.subject}"

class TimetableSlot(models.Model):
    DAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='slots')
    day = models.IntegerField(choices=DAY_CHOICES)
    period = models.IntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'timetable_slots'
        ordering = ['day', 'period']

    def __str__(self):
        return f"{self.get_day_display()} P{self.period} — {self.class_subject}"

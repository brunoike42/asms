"""
STUB — for validation only. Mirrors the field names Appendix C documents
for Student, AttendanceRecord, and ExamResult closely enough to prove the
rollup task's aggregate queries are actually correct, not just that they
don't crash. Swap for your real apps/academics/models.py before relying
on apps/networks/tasks.py in production — see the README for exactly
which field names the task assumes.
"""
from django.db import models


class Student(models.Model):
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, default="ACTIVE")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class AttendanceStatus(models.TextChoices):
    PRESENT = "PRESENT", "Present"
    ABSENT = "ABSENT", "Absent"
    LATE = "LATE", "Late"


class AttendanceRecord(models.Model):
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=AttendanceStatus.choices)


class ExamResult(models.Model):
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    marks = models.DecimalField(max_digits=5, decimal_places=2)
    passed = models.BooleanField(default=True)

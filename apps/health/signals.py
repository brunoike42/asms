"""
ASMS Health — Signals
Auto-provisions a StudentHealthRecord whenever a new Student is created,
ensuring every student always has a medical profile from day one.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.students.models import Student
from .models import StudentHealthRecord
@receiver(post_save, sender=Student)
def create_health_record_for_new_student(sender, instance, created, **kwargs):
    if created:
        StudentHealthRecord.objects.get_or_create(
            tenant=instance.tenant,
            student=instance,
        )

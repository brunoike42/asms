"""
ASMS Canteen — Signals
Auto-provisions a MealAccount whenever a new Student is created,
matching Spec Section 3 Stage 2 (Enrolment & Class Placement):
"Library, canteen, and transport accounts created."
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.students.models import Student
from .models import MealAccount
@receiver(post_save, sender=Student)
def create_meal_account_for_new_student(sender, instance, created, **kwargs):
    if created:
        MealAccount.objects.create(tenant=instance.tenant, student=instance, balance=0)

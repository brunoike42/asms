"""
ASMS Admissions Module
Manages the full application-to-enrolment workflow.
"""
from django.db import models
from apps.core.models import TenantModel


class AdmissionApplication(TenantModel):
    class StatusChoices(models.TextChoices):
        DRAFT     = 'draft',     'Draft / Incomplete'
        SUBMITTED = 'submitted', 'Submitted — Awaiting Review'
        SHORTLISTED = 'shortlisted', 'Shortlisted — Interview'
        ACCEPTED  = 'accepted',  'Accepted — Offer Made'
        ENROLLED  = 'enrolled',  'Enrolled — Converted to Student'
        REJECTED  = 'rejected',  'Rejected'
        WITHDRAWN = 'withdrawn', 'Withdrawn by Applicant'

    # Applicant Details
    first_name    = models.CharField(max_length=100)
    middle_name   = models.CharField(max_length=100, blank=True)
    last_name     = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    gender        = models.CharField(max_length=1, choices=[('M','Male'),('F','Female')])
    nationality   = models.CharField(max_length=50, default='Ugandan')

    # Applied For
    applying_for_level = models.ForeignKey(
        'students.ClassLevel', on_delete=models.PROTECT,
        related_name='applications', null=True, blank=True
    )
    applying_for_year  = models.ForeignKey(
        'core.AcademicYear', on_delete=models.PROTECT,
        related_name='applications', null=True, blank=True
    )

    # Guardian Info (at application stage)
    guardian_name   = models.CharField(max_length=200)
    guardian_phone  = models.CharField(max_length=20)
    guardian_email  = models.EmailField(blank=True)
    guardian_relationship = models.CharField(max_length=50, blank=True)

    # Previous School
    previous_school      = models.CharField(max_length=200, blank=True)
    previous_class       = models.CharField(max_length=50, blank=True)
    previous_school_results = models.TextField(blank=True)

    # Workflow
    status        = models.CharField(max_length=20, choices=StatusChoices.choices,
                                     default=StatusChoices.SUBMITTED)
    application_number = models.CharField(max_length=20, unique=True, blank=True)
    applied_date  = models.DateField(auto_now_add=True)
    interview_date = models.DateField(null=True, blank=True)
    decision_date = models.DateField(null=True, blank=True)
    decision_by   = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='admission_decisions')
    decision_notes = models.TextField(blank=True)
    offer_expiry  = models.DateField(null=True, blank=True)

    # When accepted → converted to student
    converted_student = models.OneToOneField(
        'students.Student', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='application'
    )

    class Meta:
        db_table  = 'admissions_application'
        ordering  = ['-applied_date']
        verbose_name = 'Admission Application'

    def __str__(self):
        return f'{self.first_name} {self.last_name} — {self.get_status_display()}'

    def get_full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(p for p in parts if p)

    def save(self, *args, **kwargs):
        if not self.application_number:
            import random, string
            self.application_number = 'APP-' + ''.join(random.choices(string.digits, k=6))
        super().save(*args, **kwargs)

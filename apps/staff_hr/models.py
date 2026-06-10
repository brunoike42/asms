from django.db import models
from apps.core.models import Tenant, TenantManager
from apps.academics.models import Department
from django.conf import settings

class StaffProfile(models.Model):
    EMPLOYMENT_CHOICES = [
        ('permanent', 'Permanent'), ('contract', 'Contract'), ('probation', 'Probation'),
        ('volunteer', 'Volunteer'), ('retired', 'Retired'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='staff_profile')
    staff_no = models.CharField(max_length=20, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_CHOICES, default='permanent')
    date_joined = models.DateField(null=True, blank=True)
    national_id = models.CharField(max_length=30, blank=True)
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=30, blank=True)
    next_of_kin_name = models.CharField(max_length=200, blank=True)
    next_of_kin_phone = models.CharField(max_length=20, blank=True)
    qualifications = models.TextField(blank=True)
    specialisation = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'staff_profiles'

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.designation or self.user.role})"

class LeaveType(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    days_allowed = models.IntegerField(default=21)
    is_paid = models.BooleanField(default=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'leave_types'

    def __str__(self):
        return self.name

class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('approved', 'Approved'),
        ('rejected', 'Rejected'), ('cancelled', 'Cancelled'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'leave_requests'
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.staff} — {self.leave_type} ({self.start_date} to {self.end_date})"

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1

class CPDRecord(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='cpd_records')
    title = models.CharField(max_length=200)
    institution = models.CharField(max_length=200, blank=True)
    cpd_type = models.CharField(max_length=100, choices=[
        ('workshop', 'Workshop'), ('seminar', 'Seminar'), ('course', 'Course'),
        ('conference', 'Conference'), ('online', 'Online Training'),
    ], default='workshop')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    hours = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    certificate = models.FileField(upload_to='cpd_certificates/', blank=True, null=True)
    notes = models.TextField(blank=True)
    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'cpd_records'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.staff} — {self.title}"

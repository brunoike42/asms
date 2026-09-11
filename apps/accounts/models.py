"""
ASMS Custom User Model
Supports all 12 roles defined in the ASMS v3.0 specification.
One User belongs to one Tenant (school).
Platform Super Admin has is_superuser=True and no tenant.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.RoleChoices.PLATFORM_ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Single user model for all 12 roles in ASMS.
    Role determines what the user can see and do.
    """

    class RoleChoices(models.TextChoices):
        # Platform level
        PLATFORM_ADMIN  = 'platform_admin',  'Platform Super Admin'
        NETWORK_ADMIN   = 'network_admin',   'Network Admin'
        # School system roles
        SCHOOL_ADMIN    = 'school_admin',    'School Super Admin'
        PRINCIPAL       = 'principal',       'Principal'
        TEACHER         = 'teacher',         'Teacher'
        ACCOUNTANT      = 'accountant',      'Accountant'
        COUNSELLOR      = 'counsellor',      'Counsellor'
        LIBRARIAN       = 'librarian',       'Librarian'
        RECEPTIONIST    = 'receptionist',    'Receptionist'
        NURSE           = 'nurse',           'Nurse'
        # App-facing roles (portal users)
        PARENT          = 'parent',          'Parent / Guardian'
        STUDENT         = 'student',         'Student'

    # ── Core Fields ──────────────────────────────────────────────
    email        = models.EmailField(unique=True)
    first_name   = models.CharField(max_length=100)
    last_name    = models.CharField(max_length=100)
    role         = models.CharField(max_length=20, choices=RoleChoices.choices,
                                    default=RoleChoices.TEACHER)

    # ── Tenant Link ───────────────────────────────────────────────
    tenant       = models.ForeignKey(
        'core.Tenant', on_delete=models.CASCADE,
        null=True, blank=True, related_name='users',
        help_text='Null for Platform Super Admin only'
    )

    # ── Profile ───────────────────────────────────────────────────
    phone        = models.CharField(max_length=20, blank=True)
    photo        = models.ImageField(upload_to='users/photos/', null=True, blank=True)
    date_joined  = models.DateTimeField(default=timezone.now)
    last_login   = models.DateTimeField(null=True, blank=True)

    # ── Flags ─────────────────────────────────────────────────────
    is_active    = models.BooleanField(default=True)
    is_staff     = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=True,
                           help_text='Force password change on first login')

    # ── Notification Preferences ──────────────────────────────────
    notify_sms    = models.BooleanField(default=True)
    notify_email  = models.BooleanField(default=True)
    notify_push   = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table            = 'accounts_user'
        verbose_name        = 'User'
        verbose_name_plural = 'Users'
        ordering            = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.get_full_name()} ({self.get_role_display()})'

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def get_short_name(self):
        return self.first_name

    # ── Role Helpers ──────────────────────────────────────────────

    @property
    def is_platform_admin(self):
        return self.role == self.RoleChoices.PLATFORM_ADMIN or self.is_superuser

    @property
    def is_school_admin(self):
        return self.role in (
            self.RoleChoices.SCHOOL_ADMIN,
            self.RoleChoices.PRINCIPAL,
        )

    @property
    def is_staff_member(self):
        """True for all school staff (not parents/students)."""
        return self.role not in (
            self.RoleChoices.PARENT,
            self.RoleChoices.STUDENT,
            self.RoleChoices.PLATFORM_ADMIN,
            self.RoleChoices.NETWORK_ADMIN,
        )

    @property
    def is_portal_user(self):
        """True for parent and student portal users."""
        return self.role in (self.RoleChoices.PARENT, self.RoleChoices.STUDENT)

    def can_access_finance(self):
        return self.role in (
            self.RoleChoices.SCHOOL_ADMIN,
            self.RoleChoices.PRINCIPAL,
            self.RoleChoices.ACCOUNTANT,
            
        )

    def can_manage_students(self):
        return self.role in (
            self.RoleChoices.SCHOOL_ADMIN,
            self.RoleChoices.PRINCIPAL,
            self.RoleChoices.TEACHER,
            self.RoleChoices.RECEPTIONIST,
            
        )

    def get_dashboard_url(self):
        """Returns the correct dashboard URL based on role."""
        role_urls = {
            self.RoleChoices.PLATFORM_ADMIN: '/dashboard/',
            self.RoleChoices.SCHOOL_ADMIN:   '/dashboard/',
            self.RoleChoices.PRINCIPAL:       '/dashboard/',
            self.RoleChoices.TEACHER:        '/dashboard/teacher/',
            self.RoleChoices.ACCOUNTANT:     '/dashboard/finance/',
            self.RoleChoices.COUNSELLOR:     '/dashboard/welfare/',
            self.RoleChoices.LIBRARIAN:      '/dashboard/library/',
            self.RoleChoices.PARENT:         '/parent/',
            self.RoleChoices.STUDENT:        '/portal/',
            self.RoleChoices.NETWORK_ADMIN: '/network-admin/',
        }
        return role_urls.get(self.role, '/dashboard/')

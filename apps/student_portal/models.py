"""
ASMS — Student Portal Models
Phase 3 — new models that support the enhanced portal.

Builds on Phase 1 & 2 data (Student, Term, FeeInvoice, ExamResult, etc.).
All models carry tenant_id and use TenantManager for automatic row-level isolation.

Additions benchmarked from Makerere University AIMS portal:
  - TermEnrollment          (semester self-enrollment, Makerere Step IV)
  - CourseUnitRegistration  (subject/unit selection per term, Makerere Step VI)
  - ExamPermit              (auto-generated permit when clearance conditions met)
  - ExamAppeal              (formal result re-mark request, Makerere appeals)
  - ProgramChangeRequest    (stream/programme change, Makerere Step VIII)
  - LeaveOfAbsenceRequest   (deferment / dead year, Makerere option)
  - AcademicClearanceItem   (graduation clearance checklist)
  - StudentClearance        (per-student clearance summary)
  - AcademicCalendarEvent   (structured key dates, Makerere academic calendar)
"""
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator


# ---------------------------------------------------------------------------
# Shared base manager (mirrors existing TenantManager pattern from Phase 1/2)
# ---------------------------------------------------------------------------
class TenantManager(models.Manager):
    """Filters every QuerySet to the active tenant stored in thread-local."""
    def get_queryset(self):
        from apps.core.models import get_current_tenant
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant:
            return qs.filter(tenant_id=tenant.id)
        return qs


class AllObjectsManager(models.Manager):
    """Bypass tenant filter — for admin / cross-tenant tasks only."""
    pass


# ---------------------------------------------------------------------------
# 1. Term Enrollment
#    Student confirms enrollment each term/semester.
#    Source inspiration: Makerere AIMS Step IV (Semester Enrollment)
# ---------------------------------------------------------------------------
class TermEnrollment(models.Model):
    """Tracks whether a student has formally enrolled for a given term."""

    class Status(models.TextChoices):
        NEW          = 'new',         _('New Student')
        CONTINUING   = 'continuing',  _('Continuing Student')
        RETAKE       = 'retake',      _('Completed with Retakes')
        DEFERRAL     = 'deferral',    _('Deferred / Dead Year')
        COMPLETED    = 'completed',   _('Programme Completed')

    tenant        = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, db_index=True)
    student       = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='portal_term_enrollments')
    term          = models.ForeignKey('core.Term', on_delete=models.CASCADE, related_name='portal_term_enrollments')
    status        = models.CharField(max_length=20, choices=Status.choices, default=Status.CONTINUING)
    study_year    = models.PositiveSmallIntegerField(help_text='Year of study (1, 2, 3…)')
    enrolled_at   = models.DateTimeField(auto_now_add=True)
    confirmed_at  = models.DateTimeField(null=True, blank=True)
    is_confirmed  = models.BooleanField(default=False)
    notes         = models.TextField(blank=True)

    objects     = TenantManager()
    all_objects = AllObjectsManager()

    class Meta:
        unique_together = ('tenant', 'student', 'term')
        ordering = ['-term__start_date']
        verbose_name = 'Term Enrollment'

    def confirm(self):
        self.is_confirmed = True
        self.confirmed_at = timezone.now()
        self.save(update_fields=['is_confirmed', 'confirmed_at'])

    def __str__(self):
        return f"{self.student} — {self.term} ({self.get_status_display()})"


# ---------------------------------------------------------------------------
# 2. Course Unit / Subject Registration
#    For tertiary: students select specific course units per semester.
#    For secondary: elective/option subject selection.
#    Source inspiration: Makerere AIMS Step VI (Course Unit Selection)
# ---------------------------------------------------------------------------
class CourseUnitRegistration(models.Model):
    """A student's registration for a specific subject/course unit in a term."""

    class PaperType(models.TextChoices):
        NORMAL         = 'normal',        _('Normal Paper')
        RETAKE         = 'retake',        _('Retake')
        SUPPLEMENTARY  = 'supplementary', _('Supplementary')
        MISSED         = 'missed',        _('Missed Paper')
        ELECTIVE       = 'elective',      _('Elective Subject')

    tenant      = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, db_index=True)
    enrollment  = models.ForeignKey(TermEnrollment, on_delete=models.CASCADE, related_name='course_registrations')
    subject     = models.ForeignKey('academics.Subject', on_delete=models.CASCADE, related_name='course_registrations')
    paper_type  = models.CharField(max_length=20, choices=PaperType.choices, default=PaperType.NORMAL)
    registered_at = models.DateTimeField(auto_now_add=True)
    is_active   = models.BooleanField(default=True)

    objects     = TenantManager()
    all_objects = AllObjectsManager()

    class Meta:
        unique_together = ('tenant', 'enrollment', 'subject')
        ordering = ['subject__name']
        verbose_name = 'Course Unit Registration'

    def __str__(self):
        return f"{self.enrollment.student} — {self.subject.name} ({self.get_paper_type_display()})"


# ---------------------------------------------------------------------------
# 3. Exam Permit
#    Auto-generated when student meets fee & enrollment clearance conditions.
#    Source inspiration: Makerere semester registration after fee payment.
# ---------------------------------------------------------------------------
class ExamPermit(models.Model):
    """Exam sitting permit — generated when registration conditions are met."""

    class Status(models.TextChoices):
        PENDING   = 'pending',   _('Pending')
        ISSUED    = 'issued',    _('Issued')
        BLOCKED   = 'blocked',   _('Blocked — Clearance Incomplete')
        REVOKED   = 'revoked',   _('Revoked')

    tenant        = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, db_index=True)
    enrollment    = models.OneToOneField(TermEnrollment, on_delete=models.CASCADE, related_name='exam_permit')
    permit_number = models.CharField(max_length=30, unique=True)
    status        = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    issued_at     = models.DateTimeField(null=True, blank=True)
    blocked_reason = models.TextField(blank=True, help_text='Reason if blocked (e.g. unpaid fees)')
    pdf_path      = models.CharField(max_length=500, blank=True, help_text='Cloudinary PDF path')

    objects     = TenantManager()
    all_objects = AllObjectsManager()

    class Meta:
        ordering = ['-issued_at']
        verbose_name = 'Exam Permit'

    def issue(self, pdf_path=''):
        self.status    = self.Status.ISSUED
        self.issued_at = timezone.now()
        self.pdf_path  = pdf_path
        self.save(update_fields=['status', 'issued_at', 'pdf_path'])

    def __str__(self):
        return f"Permit {self.permit_number} — {self.enrollment}"


# ---------------------------------------------------------------------------
# 4. Exam Appeal
#    Student submits formal re-mark / result query for a specific subject.
#    Source inspiration: Makerere Senate Examinations Committee appeal process.
# ---------------------------------------------------------------------------
class ExamAppeal(models.Model):
    """Formal appeal lodged by a student against a published exam result."""

    class AppealType(models.TextChoices):
        REMARK      = 'remark',      _('Re-mark Request')
        CLERICAL    = 'clerical',    _('Clerical Error')
        MISSING     = 'missing',     _('Missing Result')
        QUERY       = 'query',       _('General Query')

    class Status(models.TextChoices):
        SUBMITTED   = 'submitted',   _('Submitted')
        ACKNOWLEDGED = 'acknowledged', _('Acknowledged')
        UNDER_REVIEW = 'under_review', _('Under Review')
        RESOLVED    = 'resolved',    _('Resolved')
        REJECTED    = 'rejected',    _('Rejected')

    tenant          = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, db_index=True)
    student         = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='exam_appeals')
    term            = models.ForeignKey('core.Term', on_delete=models.CASCADE)
    subject         = models.ForeignKey('academics.Subject', on_delete=models.CASCADE)
    appeal_type     = models.CharField(max_length=15, choices=AppealType.choices)
    status          = models.CharField(max_length=15, choices=Status.choices, default=Status.SUBMITTED)
    original_marks  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    statement       = models.TextField(help_text="Student's written grounds for the appeal")
    admin_response  = models.TextField(blank=True)
    revised_marks   = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    submitted_at    = models.DateTimeField(auto_now_add=True)
    resolved_at     = models.DateTimeField(null=True, blank=True)
    resolved_by     = models.ForeignKey('staff_hr.StaffProfile', on_delete=models.SET_NULL, null=True, blank=True)
    reference_number = models.CharField(max_length=30, unique=True, blank=True)

    objects     = TenantManager()
    all_objects = AllObjectsManager()

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Exam Appeal'

    def save(self, *args, **kwargs):
        if not self.reference_number:
            import uuid
            self.reference_number = f"APP-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def resolve(self, admin_response, revised_marks, resolved_by):
        self.admin_response = admin_response
        self.revised_marks  = revised_marks
        self.resolved_by    = resolved_by
        self.status         = self.Status.RESOLVED
        self.resolved_at    = timezone.now()
        self.save(update_fields=['admin_response', 'revised_marks', 'resolved_by', 'status', 'resolved_at'])

    def __str__(self):
        return f"Appeal {self.reference_number} — {self.student} ({self.subject})"


# ---------------------------------------------------------------------------
# 5. Programme / Stream Change Request
#    Tertiary: full programme change. Secondary: stream change (sci/arts).
#    Source inspiration: Makerere "Change of Programme" portal action.
# ---------------------------------------------------------------------------
class ProgramChangeRequest(models.Model):
    """Student application to change their programme or class stream."""

    class Status(models.TextChoices):
        PENDING   = 'pending',   _('Pending Review')
        APPROVED  = 'approved',  _('Approved')
        REJECTED  = 'rejected',  _('Rejected')

    tenant            = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, db_index=True)
    student           = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='program_changes')
    current_class     = models.ForeignKey('students.ClassRoom', on_delete=models.PROTECT, related_name='change_from')
    requested_class   = models.ForeignKey('students.ClassRoom', on_delete=models.PROTECT, related_name='change_to')
    reason            = models.TextField(help_text="Student's stated reason for the change")
    supporting_document = models.CharField(max_length=500, blank=True, help_text='Cloudinary file path')
    status            = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    admin_comment     = models.TextField(blank=True)
    submitted_at      = models.DateTimeField(auto_now_add=True)
    reviewed_at       = models.DateTimeField(null=True, blank=True)
    reviewed_by       = models.ForeignKey('staff_hr.StaffProfile', on_delete=models.SET_NULL, null=True, blank=True)

    objects     = TenantManager()
    all_objects = AllObjectsManager()

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Programme Change Request'

    def __str__(self):
        return f"{self.student}: {self.current_class} → {self.requested_class} ({self.get_status_display()})"


# ---------------------------------------------------------------------------
# 6. Leave of Absence / Deferment Request
#    Source inspiration: Makerere "Dead Year" / Deferment process.
# ---------------------------------------------------------------------------
class LeaveOfAbsenceRequest(models.Model):
    """Student application for temporary suspension of studies (dead year)."""

    class LeaveType(models.TextChoices):
        MEDICAL      = 'medical',      _('Medical Leave')
        FINANCIAL    = 'financial',    _('Financial Hardship')
        PERSONAL     = 'personal',     _('Personal Reasons')
        BEREAVEMENT  = 'bereavement',  _('Bereavement')
        OFFICIAL     = 'official',     _('Official / Scholarship')
        OTHER        = 'other',        _('Other')

    class Status(models.TextChoices):
        PENDING   = 'pending',   _('Pending')
        APPROVED  = 'approved',  _('Approved')
        REJECTED  = 'rejected',  _('Rejected')
        REINSTATED = 'reinstated', _('Reinstated')

    tenant            = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, db_index=True)
    student           = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='leave_requests')
    leave_type        = models.CharField(max_length=15, choices=LeaveType.choices)
    from_term         = models.ForeignKey('core.Term', on_delete=models.PROTECT, related_name='leave_from')
    expected_return_term = models.ForeignKey('core.Term', on_delete=models.PROTECT, related_name='leave_return', null=True, blank=True)
    reason            = models.TextField()
    supporting_document = models.CharField(max_length=500, blank=True)
    status            = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    admin_comment     = models.TextField(blank=True)
    submitted_at      = models.DateTimeField(auto_now_add=True)
    reviewed_at       = models.DateTimeField(null=True, blank=True)
    reviewed_by       = models.ForeignKey('staff_hr.StaffProfile', on_delete=models.SET_NULL, null=True, blank=True)

    objects     = TenantManager()
    all_objects = AllObjectsManager()

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Leave of Absence Request'

    def __str__(self):
        return f"{self.student} — Leave from {self.from_term} ({self.get_status_display()})"


# ---------------------------------------------------------------------------
# 7. Academic Clearance
#    Graduation clearance checklist (library, finance, departmental, etc.)
#    Source inspiration: Makerere registration clearance requirements.
# ---------------------------------------------------------------------------
class AcademicClearanceItem(models.Model):
    """A clearance requirement that must be satisfied (e.g. library, finance)."""

    class Department(models.TextChoices):
        LIBRARY    = 'library',    _('Library')
        FINANCE    = 'finance',    _('Finance / Accounts')
        ACADEMICS  = 'academics',  _('Academic Registrar')
        SPORTS     = 'sports',     _('Sports / PE')
        HEALTH     = 'health',     _('Health / Nurse')
        HOSTEL     = 'hostel',     _('Hostel / Boarding')
        IT         = 'it',         _('ICT Department')
        CUSTOM     = 'custom',     _('Other Department')

    tenant      = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, db_index=True)
    name        = models.CharField(max_length=100)
    department  = models.CharField(max_length=15, choices=Department.choices)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    order       = models.PositiveSmallIntegerField(default=0)

    objects     = TenantManager()
    all_objects = AllObjectsManager()

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_department_display()})"


class StudentClearance(models.Model):
    """Per-student clearance status for a specific academic year."""

    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', _('In Progress')
        CLEARED     = 'cleared',     _('Cleared')
        BLOCKED     = 'blocked',     _('Blocked')

    tenant          = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, db_index=True)
    student         = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='clearances')
    academic_year   = models.ForeignKey('core.AcademicYear', on_delete=models.CASCADE)
    overall_status  = models.CharField(max_length=15, choices=Status.choices, default=Status.IN_PROGRESS)
    requested_at    = models.DateTimeField(auto_now_add=True)
    cleared_at      = models.DateTimeField(null=True, blank=True)
    notes           = models.TextField(blank=True)

    objects     = TenantManager()
    all_objects = AllObjectsManager()

    class Meta:
        unique_together = ('tenant', 'student', 'academic_year')
        ordering = ['-academic_year__start_date']

    def __str__(self):
        return f"Clearance — {self.student} ({self.academic_year})"


class StudentClearanceItemStatus(models.Model):
    """Whether a student has been cleared for a specific clearance item."""

    class Status(models.TextChoices):
        PENDING  = 'pending',   _('Pending')
        CLEARED  = 'cleared',   _('Cleared')
        BLOCKED  = 'blocked',   _('Blocked')
        WAIVED   = 'waived',    _('Waived')

    clearance   = models.ForeignKey(StudentClearance, on_delete=models.CASCADE, related_name='item_statuses')
    item        = models.ForeignKey(AcademicClearanceItem, on_delete=models.CASCADE)
    status      = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    cleared_by  = models.ForeignKey('staff_hr.StaffProfile', on_delete=models.SET_NULL, null=True, blank=True)
    cleared_at  = models.DateTimeField(null=True, blank=True)
    remarks     = models.TextField(blank=True)

    class Meta:
        unique_together = ('clearance', 'item')
        ordering = ['item__order']


# ---------------------------------------------------------------------------
# 8. Academic Calendar Event
#    Structured key dates visible to students in the portal calendar.
#    Source inspiration: Makerere AIMS "View Academic Calendar" feature.
# ---------------------------------------------------------------------------
class AcademicCalendarEvent(models.Model):
    """A named date or date range on the school's academic calendar."""

    class EventType(models.TextChoices):
        TERM_START      = 'term_start',      _('Term / Semester Start')
        TERM_END        = 'term_end',        _('Term / Semester End')
        EXAM_PERIOD     = 'exam_period',     _('Examination Period')
        REGISTRATION    = 'registration',    _('Registration Window')
        FEE_DEADLINE    = 'fee_deadline',    _('Fee Payment Deadline')
        HOLIDAY         = 'holiday',         _('Public Holiday / Break')
        SUBMISSION      = 'submission',      _('Assignment / Project Deadline')
        GRADUATION      = 'graduation',      _('Graduation / Prize Day')
        SPORTS          = 'sports',          _('Sports Day / Competition')
        OPEN_DAY        = 'open_day',        _('Open Day / Visiting Day')
        ANNOUNCEMENT    = 'announcement',    _('General School Event')

    class Audience(models.TextChoices):
        ALL         = 'all',        _('All Students')
        PRIMARY     = 'primary',    _('Primary Only')
        SECONDARY   = 'secondary',  _('Secondary Only')
        TERTIARY    = 'tertiary',   _('Tertiary Only')
        CLASS       = 'class',      _('Specific Class/Year')

    tenant      = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, db_index=True)
    academic_year = models.ForeignKey('core.AcademicYear', on_delete=models.CASCADE, null=True, blank=True)
    term        = models.ForeignKey('core.Term', on_delete=models.CASCADE, null=True, blank=True)
    title       = models.CharField(max_length=200)
    event_type  = models.CharField(max_length=20, choices=EventType.choices)
    description = models.TextField(blank=True)
    start_date  = models.DateField()
    end_date    = models.DateField(null=True, blank=True, help_text='Leave blank for single-day events')
    audience    = models.CharField(max_length=15, choices=Audience.choices, default=Audience.ALL)
    is_published = models.BooleanField(default=True)
    created_by  = models.ForeignKey('staff_hr.StaffProfile', on_delete=models.SET_NULL, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    objects     = TenantManager()
    all_objects = AllObjectsManager()

    class Meta:
        ordering = ['start_date']
        verbose_name = 'Academic Calendar Event'

    @property
    def is_single_day(self):
        return self.end_date is None or self.end_date == self.start_date

    @property
    def duration_days(self):
        if self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 1

    def __str__(self):
        return f"{self.title} ({self.start_date})"


# ---------------------------------------------------------------------------
# 9. Portal Notification
#    Persistent in-portal notifications for a student (in-app bell icon feed).
#    Complements the existing Communication SMS/email system from Phase 1.
# ---------------------------------------------------------------------------
class PortalNotification(models.Model):
    """A notification item displayed in the student's in-portal bell feed."""

    class Category(models.TextChoices):
        ACADEMIC    = 'academic',    _('Academic')
        FINANCE     = 'finance',     _('Finance')
        ATTENDANCE  = 'attendance',  _('Attendance')
        DISCIPLINE  = 'discipline',  _('Discipline')
        WELFARE     = 'welfare',     _('Welfare')
        DOCUMENT    = 'document',    _('Document Ready')
        SYSTEM      = 'system',      _('System')
        GENERAL     = 'general',     _('General')

    tenant      = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, db_index=True)
    student     = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='portal_notifications')
    category    = models.CharField(max_length=15, choices=Category.choices, default=Category.GENERAL)
    title       = models.CharField(max_length=200)
    body        = models.TextField()
    action_url  = models.CharField(max_length=300, blank=True, help_text='Portal URL to navigate to')
    is_read     = models.BooleanField(default=False)
    read_at     = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    objects     = TenantManager()
    all_objects = AllObjectsManager()

    class Meta:
        ordering = ['-created_at']

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def __str__(self):
        return f"[{self.category}] {self.title} → {self.student}"


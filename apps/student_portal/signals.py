"""
ASMS — Student Portal Signals
Phase 3

Listens to Phase 1 & 2 events and:
  - Creates TermEnrollment when a new Term becomes active
  - Issues ExamPermit when enrollment is confirmed + fee threshold met
  - Creates PortalNotification for key events (results, absence, fee)
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# 1. Auto-create TermEnrollment for active students when a Term starts
#    Triggered when: Term.is_active is set True (or by Celery Beat daily check)
# ─────────────────────────────────────────────────────────────────────────────
@receiver(post_save, sender='core.Term')
def create_enrollments_for_new_term(sender, instance, created, **kwargs):
    """When a term is saved as current, create draft enrollments for all active students."""
    if not instance.is_current:
        return

    from apps.students.models import Student
    from .models import TermEnrollment

    students = Student.objects.filter(
        status='active',
        tenant=instance.tenant,
    )
    for student in students:
        TermEnrollment.objects.get_or_create(
            tenant=instance.tenant,
            student=student,
            term=instance,
            defaults={
                'status':     TermEnrollment.Status.CONTINUING,
                'study_year': student.current_year_of_study or 1,
            }
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Auto-issue ExamPermit when TermEnrollment is confirmed
# ─────────────────────────────────────────────────────────────────────────────
@receiver(post_save, sender='student_portal.TermEnrollment')
def issue_exam_permit_on_confirmation(sender, instance, **kwargs):
    """Issue (or block) an ExamPermit when enrollment is confirmed."""
    if not instance.is_confirmed:
        return

    from apps.finance.models import FeeInvoice, Payment
    from django.db.models import Sum
    from .models import ExamPermit
    import uuid

    # Check fee threshold (must have paid at least 60%)
    invoices = FeeInvoice.objects.filter(student=instance.student, term=instance.term)
    total_billed = sum(inv.total for inv in invoices)
    total_paid   = Payment.objects.filter(
        invoice__in=invoices, status='success'
    ).aggregate(s=Sum('amount'))['s'] or 0

    fee_pct = (total_paid / total_billed * 100) if total_billed > 0 else 0

    permit, _ = ExamPermit.objects.get_or_create(
        enrollment=instance,
        defaults={
            'permit_number': f"EXP-{instance.tenant_id}-{instance.term.id}-"
                              f"{instance.student.student_id}-{uuid.uuid4().hex[:4].upper()}",
        }
    )

    if permit.status in ('issued', 'revoked'):
        return  # Don't re-process

    if fee_pct >= 60:
        permit.issue()
        _notify_student(
            instance.student,
            category='document',
            title='Exam Permit Issued',
            body=f'Your exam permit for {instance.term} has been issued. Download it from the portal.',
            url='/portal/exam-permit/',
        )
    else:
        permit.status         = ExamPermit.Status.BLOCKED
        permit.blocked_reason = (
            f"Your fee payment is only {fee_pct:.0f}% of the required amount. "
            f"Pay at least 60% of your fees to receive your exam permit."
        )
        permit.save(update_fields=['status', 'blocked_reason'])


# ─────────────────────────────────────────────────────────────────────────────
# 3. Portal notification when exam results are published (Phase 2 — ExamResult)
# ─────────────────────────────────────────────────────────────────────────────
@receiver(post_save, sender='exams.TermReport')
def notify_student_results_published(sender, instance, created, **kwargs):
    """Push a portal notification when a report card is generated for a student."""
    if not created:
        return
    _notify_student(
        instance.student,
        category='academic',
        title='Results Published',
        body=f'Your results for {instance.term} are now available. '
             f'View your report card from My Results.',
        url='/portal/results/',
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Portal notification when a student is marked absent (Phase 1 — Attendance)
# ─────────────────────────────────────────────────────────────────────────────
@receiver(post_save, sender='attendance.AttendanceRecord')
def notify_student_absent(sender, instance, created, **kwargs):
    """Notify the student portal when they are marked absent."""
    if not created or instance.status != 'absent':
        return
    _notify_student(
        instance.student,
        category='attendance',
        title='Absence Recorded',
        body=f'You were marked absent on {instance.date.strftime("%d %b %Y")}. '
             f'Submit an excuse note if you have a valid reason.',
        url='/portal/attendance/excuse/',
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Portal notification when a discipline incident is logged (Phase 2)
# ─────────────────────────────────────────────────────────────────────────────
@receiver(post_save, sender='discipline.DisciplineIncident')
def notify_student_incident(sender, instance, created, **kwargs):
    if not created:
        return
    _notify_student(
        instance.student,
        category='discipline',
        title='Discipline Incident Logged',
        body=f'A {instance.get_incident_type_display()} incident was recorded on '
             f'{instance.date.strftime("%d %b %Y")}. View details in My Merits.',
        url='/portal/merits/',
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Portal notification when a fee payment is confirmed (Phase 1 — Finance)
# ─────────────────────────────────────────────────────────────────────────────
@receiver(post_save, sender='finance.Payment')
def notify_student_payment_confirmed(sender, instance, created, **kwargs):
    if not created or instance.status != 'success':
        return
    _notify_student(
        instance.invoice.student,
        category='finance',
        title='Payment Confirmed',
        body=f'Payment of {instance.amount:,.0f} UGX received. '
             f'Receipt #{instance.id} is available in your fee account.',
        url='/portal/fees/',
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7. Portal notification on ExamAppeal status change
# ─────────────────────────────────────────────────────────────────────────────
@receiver(pre_save, sender='student_portal.ExamAppeal')
def notify_appeal_status_change(sender, instance, **kwargs):
    """Detect status transitions and notify the student."""
    if not instance.pk:
        return  # New object — no previous state
    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if previous.status != instance.status:
        status_messages = {
            'acknowledged':  'Your appeal has been acknowledged and will be reviewed soon.',
            'under_review':  'Your appeal is now under review by the Academic Registrar.',
            'resolved':      f'Your appeal ({instance.reference_number}) has been resolved. '
                             f'Check the outcome in Exam Appeals.',
            'rejected':      f'Your appeal ({instance.reference_number}) was not upheld. '
                             f'Contact the Registrar for further information.',
        }
        msg = status_messages.get(instance.status)
        if msg:
            _notify_student(
                instance.student,
                category='academic',
                title=f'Appeal Update — {instance.reference_number}',
                body=msg,
                url='/portal/appeals/',
            )


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────
def _notify_student(student, category, title, body, url=''):
    """Create a PortalNotification for a student (fire-and-forget)."""
    from .models import PortalNotification
    try:
        PortalNotification.objects.create(
            tenant=student.tenant,
            student=student,
            category=category,
            title=title,
            body=body,
            action_url=url,
        )
    except Exception:
        pass  # Never let a notification failure break the main flow

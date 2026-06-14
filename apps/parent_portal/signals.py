"""
Parent portal signals.

Listens for events across the platform and creates ParentNotification
records so parents see real-time updates in their portal.

Wired up from:
  - discipline post_save → notify on new incident
  - attendance post_save → notify on absence
  - payments.payment_confirmed → notify on payment success
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
#  Discipline Incident → Parent Notification
# ──────────────────────────────────────────────────────────

def connect_discipline_signal():
    """Connect to discipline post_save — called from AppConfig.ready()."""
    try:
        from apps.discipline.models import DisciplineIncident

        @receiver(post_save, sender=DisciplineIncident, weak=False,
                  dispatch_uid='parent_portal_discipline_notify')
        def on_incident_created(sender, instance, created, **kwargs):
            if not created:
                return
            try:
                _notify_parent_incident(instance)
            except Exception as e:
                logger.warning(f'Parent notification failed for incident {instance.pk}: {e}')

    except Exception as e:
        logger.debug(f'Could not connect discipline signal: {e}')


def _notify_parent_incident(incident):
    """Create a parent portal notification for a new discipline incident."""
    from .models import ParentNotification
    from .utils import _get_parent_users_for_student

    student = incident.student
    parent_users = _get_parent_users_for_student(student)

    for parent_user in parent_users:
        is_critical = incident.severity in ('serious', 'critical')
        ParentNotification.objects.create(
            tenant      = incident.tenant,
            parent_user = parent_user,
            student     = student,
            category    = 'behaviour',
            title       = f'Discipline incident — {incident.category.name}',
            body        = (
                f'A {incident.get_severity_display().lower()} discipline incident '
                f'has been recorded for {student.first_name} on '
                f'{incident.incident_date.strftime("%d %b %Y")}. '
                f'Ref: {incident.reference_number}. Please log in for details.'
            ),
            action_url  = f'/parent/child/{student.pk}/behaviour/',
            is_urgent   = is_critical,
        )
        logger.info(
            f'Parent notification created: behaviour incident for '
            f'{student} → {parent_user.email}'
        )


# ──────────────────────────────────────────────────────────
#  Attendance Absence → Parent Notification
# ──────────────────────────────────────────────────────────

def connect_attendance_signal():
    """Connect to attendance post_save."""
    try:
        from apps.attendance.models import AttendanceRecord

        @receiver(post_save, sender=AttendanceRecord, weak=False,
                  dispatch_uid='parent_portal_attendance_notify')
        def on_attendance_marked(sender, instance, created, **kwargs):
            if not created:
                return
            if getattr(instance, 'status', '') not in ('absent', 'Absent', 'A'):
                return
            try:
                _notify_parent_absence(instance)
            except Exception as e:
                logger.warning(f'Attendance notification failed: {e}')

    except Exception as e:
        logger.debug(f'Could not connect attendance signal: {e}')


def _notify_parent_absence(record):
    """Create a parent portal notification for a student absence."""
    from .models import ParentNotification
    from .utils import _get_parent_users_for_student

    student = record.student
    parent_users = _get_parent_users_for_student(student)
    tenant = getattr(student, 'tenant', None)

    date_str = record.date.strftime('%d %b %Y') if hasattr(record.date, 'strftime') else str(record.date)

    for parent_user in parent_users:
        # Avoid duplicate notifications for same date
        already = ParentNotification.objects.filter(
            parent_user=parent_user,
            student=student,
            category='attendance',
            created_at__date=timezone.now().date(),
        ).exists()
        if already:
            continue

        ParentNotification.objects.create(
            tenant      = tenant,
            parent_user = parent_user,
            student     = student,
            category    = 'attendance',
            title       = f'{student.first_name} was marked absent',
            body        = (
                f'{student.first_name} {student.last_name} was recorded as absent on {date_str}. '
                f'If this was expected, please submit an excuse through the portal.'
            ),
            action_url  = f'/parent/child/{student.pk}/attendance/',
            is_urgent   = False,
        )


# ──────────────────────────────────────────────────────────
#  Payment Confirmed → Parent Notification
# ──────────────────────────────────────────────────────────

def connect_payment_signal():
    """Connect to the PesaPal payment_confirmed signal."""
    try:
        from apps.payments.signals import payment_confirmed
        from apps.payments.models import PesaPalTransaction

        @receiver(payment_confirmed, sender=PesaPalTransaction, weak=False,
                  dispatch_uid='parent_portal_payment_notify')
        def on_payment_confirmed(sender, transaction, **kwargs):
            try:
                _notify_parent_payment(transaction)
            except Exception as e:
                logger.warning(f'Payment notification failed: {e}')

    except Exception as e:
        logger.debug(f'Could not connect payment signal: {e}')


def _notify_parent_payment(transaction):
    """Create a parent portal notification when a payment is confirmed."""
    from .models import ParentNotification
    from .utils import _get_parent_users_for_student

    student = transaction.student
    parent_users = _get_parent_users_for_student(student)

    for parent_user in parent_users:
        ParentNotification.objects.create(
            tenant      = transaction.tenant,
            parent_user = parent_user,
            student     = student,
            category    = 'finance',
            title       = 'Payment confirmed ✓',
            body        = (
                f'Your payment of UGX {transaction.amount:,.0f} for '
                f'{student.first_name} {student.last_name} has been confirmed. '
                f'Ref: {transaction.confirmation_code or transaction.merchant_reference}.'
            ),
            action_url  = f'/parent/child/{student.pk}/fees/',
            is_urgent   = False,
        )


# ──────────────────────────────────────────────────────────
#  Merit Awarded → Parent Notification (positive, ClassDojo-style)
# ──────────────────────────────────────────────────────────

def connect_merit_signal():
    """Connect to discipline merit post_save."""
    try:
        from apps.discipline.models import MeritRecord

        @receiver(post_save, sender=MeritRecord, weak=False,
                  dispatch_uid='parent_portal_merit_notify')
        def on_merit_awarded(sender, instance, created, **kwargs):
            if not created:
                return
            try:
                _notify_parent_merit(instance)
            except Exception as e:
                logger.warning(f'Merit notification failed: {e}')

    except Exception as e:
        logger.debug(f'Could not connect merit signal: {e}')


def _notify_parent_merit(merit):
    """Create an upbeat parent notification when a merit is awarded."""
    from .models import ParentNotification
    from .utils import _get_parent_users_for_student

    student = merit.student
    parent_users = _get_parent_users_for_student(student)

    for parent_user in parent_users:
        ParentNotification.objects.create(
            tenant      = merit.tenant,
            parent_user = parent_user,
            student     = student,
            category    = 'merit',
            title       = f'🏆 {student.first_name} earned a merit!',
            body        = (
                f'{student.first_name} was recognised for '
                f'{merit.get_merit_type_display().lower()}: "{merit.title}". '
                f'+{merit.merit_points} merit point{"s" if merit.merit_points != 1 else ""}.'
            ),
            action_url  = f'/parent/child/{student.pk}/behaviour/',
            is_urgent   = False,
        )


# Connect all signals when this module is imported
connect_discipline_signal()
connect_attendance_signal()
connect_payment_signal()
connect_merit_signal()

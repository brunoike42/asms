"""
Utility functions for the discipline module.
"""
from django.utils import timezone
from django.apps import apps


def get_current_term(tenant):
    """Return the active Term for a tenant, or None."""
    try:
        AcademicYear = apps.get_model('core', 'AcademicYear')
        Term = apps.get_model('core', 'Term')
        current_year = AcademicYear.objects.get(tenant=tenant, is_current=True)
        return Term.objects.get(academic_year=current_year, is_current=True)
    except Exception:
        return None


def get_current_academic_year(tenant):
    """Return the active AcademicYear for a tenant, or None."""
    try:
        AcademicYear = apps.get_model('core', 'AcademicYear')
        return AcademicYear.objects.get(tenant=tenant, is_current=True)
    except Exception:
        return None


def count_term_incidents(student, term):
    """Return the number of active incidents for a student in a term."""
    from .models import DisciplineIncident
    if not term:
        return 0
    return DisciplineIncident.objects.filter(
        student=student, term=term
    ).exclude(status='closed').count()


def send_parent_sms(student, message, tenant=None):
    """Send an SMS to the student's primary guardian."""
    import logging
    logger = logging.getLogger(__name__)

    phone = None
    try:
        parent = student.guardians.filter(is_primary=True).first()
        if not parent:
            parent = student.guardians.first()
        if parent:
            phone = getattr(parent, 'phone_number', None) or getattr(parent, 'phone', None)
    except Exception:
        pass

    if not phone:
        logger.warning(f'No parent phone for student {student} — SMS not sent.')
        return False

    try:
        from django.conf import settings as django_settings
        at_username = getattr(django_settings, 'AT_USERNAME', None)
        at_api_key = getattr(django_settings, 'AT_API_KEY', None)
    except Exception:
        at_username = at_api_key = None

    if at_username and at_api_key:
        try:
            import africastalking
            africastalking.initialize(at_username, at_api_key)
            sms = africastalking.SMS
            response = sms.send(message, [phone])
            logger.info(f'SMS sent to {phone}: {response}')
            return True
        except Exception as e:
            logger.error(f'Africa\'s Talking SMS failed: {e}')
            return False
    else:
        logger.info(f'[SMS STUB] To: {phone} | {message}')
        return True


def notify_parent_of_incident(incident):
    """Send parent SMS about a new discipline incident."""
    student = incident.student
    school_name = getattr(incident.tenant, 'name', 'Your School')
    message = (
        f'Dear Parent, a discipline incident has been recorded for '
        f'{student.first_name} {student.last_name} at {school_name} '
        f'on {incident.incident_date.strftime("%d/%m/%Y")}. '
        f'Category: {incident.category.name}. '
        f'Please contact the school. Ref: {incident.reference_number}'
    )
    sent = send_parent_sms(student, message, incident.tenant)
    if sent:
        from .models import DisciplineIncident
        DisciplineIncident.objects.filter(pk=incident.pk).update(
            parent_notified=True,
            parent_notified_at=timezone.now(),
            parent_notification_method='sms',
        )


def raise_counselling_flag(incident, term_incident_count):
    """Auto-open a welfare case when student reaches 3+ incidents in a term."""
    from .models import DisciplineIncident
    import logging
    logger = logging.getLogger(__name__)

    if incident.counselling_flag_raised:
        return

    try:
        WelfareCase = apps.get_model('counselling', 'WelfareCase')
        current_term = get_current_term(incident.tenant)
        current_year = get_current_academic_year(incident.tenant)

        case = WelfareCase.objects.create(
            tenant=incident.tenant,
            student=incident.student,
            case_type='behavioural',
            title=f'Auto-flagged: {term_incident_count}+ discipline incidents this term',
            description=(
                f'This case was automatically opened because {incident.student} '
                f'has {term_incident_count} discipline incidents in the current term '
                f'(threshold: 3). Most recent incident: {incident.reference_number}.'
            ),
            status='open',
            priority='high',
            trigger='discipline',
            auto_opened=True,
            opened_by=incident.reported_by,
            academic_year=current_year,
            term=current_term,
        )

        DisciplineIncident.objects.filter(pk=incident.pk).update(
            counselling_flag_raised=True,
            counselling_case=case,
        )
        logger.info(
            f'Welfare case {case.reference_number} auto-opened for '
            f'{incident.student} ({term_incident_count} incidents this term)'
        )
    except Exception as e:
        logger.error(f'Failed to raise counselling flag for incident {incident.pk}: {e}')


def recompute_behaviour_summary(student, term):
    """Rebuild the StudentBehaviourSummary for a student/term."""
    from .models import DisciplineIncident, MeritRecord, StudentBehaviourSummary, DisciplineConsequence

    if not term:
        return

    incidents = DisciplineIncident.objects.filter(
        student=student, term=term
    ).exclude(status='closed')

    merits = MeritRecord.objects.filter(student=student, term=term)

    counts = {s: incidents.filter(severity=s).count()
              for s in ('minor', 'moderate', 'serious', 'critical')}

    total_demerits = sum(
        c.demerit_points or 0
        for inc in incidents
        for c in inc.consequences.filter(approval_status='completed')
        if c.consequence_type == 'demerit_points'
    )

    susp_qs = DisciplineConsequence.objects.filter(
        incident__student=student,
        incident__term=term,
        consequence_type__in=('suspension_internal', 'suspension_external'),
        approval_status='completed',
    )
    suspension_days = sum(c.duration_days or 0 for c in susp_qs)
    total_merits = sum(m.merit_points for m in merits)

    # Get tenant from student
    tenant = getattr(student, 'tenant', None)

    summary, _ = StudentBehaviourSummary.objects.get_or_create(
        student=student,
        term=term,
        defaults={'tenant': tenant}
    )
    summary.total_incidents = incidents.count()
    summary.minor_incidents = counts['minor']
    summary.moderate_incidents = counts['moderate']
    summary.serious_incidents = counts['serious']
    summary.critical_incidents = counts['critical']
    summary.total_demerit_points = total_demerits
    summary.total_merit_points = total_merits
    summary.net_behaviour_score = total_merits - total_demerits
    summary.suspensions_served = susp_qs.count()
    summary.suspension_days = suspension_days
    summary.save()

    return summary
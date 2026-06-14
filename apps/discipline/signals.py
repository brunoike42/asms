"""
Discipline module signals.

Key behaviours triggered here (per spec Appendix D.4):
1. Post-save on DisciplineIncident → send parent SMS within 30 min
2. At 3+ incidents in term → auto-open counselling case
3. Suspension consequence → require principal approval
4. Rebuild StudentBehaviourSummary on incident save
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import DisciplineIncident, DisciplineConsequence, MeritRecord
from .utils import (
    get_current_term,
    count_term_incidents,
    notify_parent_of_incident,
    raise_counselling_flag,
    recompute_behaviour_summary,
)


@receiver(post_save, sender=DisciplineIncident)
def on_incident_saved(sender, instance, created, **kwargs):
    """
    Fires after any DisciplineIncident save.
    On creation: notify parent, check for counselling threshold.
    On update: rebuild behaviour summary.
    """
    if created:
        _handle_new_incident(instance)
    _update_behaviour_summary(instance)


def _handle_new_incident(incident):
    """Process a brand-new incident."""
    import logging
    logger = logging.getLogger(__name__)

    # --- Assign current term if not set ---
    if not incident.term:
        term = get_current_term(incident.tenant)
        if term:
            DisciplineIncident.objects.filter(pk=incident.pk).update(
                term=term,
                academic_year=term.academic_year,
            )
            incident.term = term
            incident.academic_year = term.academic_year

    # --- Auto-require approval for serious/critical or category-flagged ---
    needs_approval = (
        incident.severity in ('serious', 'critical') or
        incident.category.requires_principal_approval
    )
    if needs_approval and not incident.requires_principal_approval:
        DisciplineIncident.objects.filter(pk=incident.pk).update(
            requires_principal_approval=True,
            status='awaiting_principal_approval',
        )

    # --- Notify parent via SMS (deferred to Celery in production) ---
    try:
        notify_parent_of_incident(incident)
    except Exception as e:
        logger.warning(f'Parent SMS failed for incident {incident.pk}: {e}')

    # --- Check 3+ incidents threshold → counselling flag ---
    term = incident.term
    if term:
        term_count = count_term_incidents(incident.student, term)
        if term_count >= 3 and not incident.counselling_flag_raised:
            try:
                raise_counselling_flag(incident, term_count)
            except Exception as e:
                logger.warning(f'Counselling flag failed for incident {incident.pk}: {e}')


def _update_behaviour_summary(incident):
    """Rebuild the StudentBehaviourSummary for this student's term."""
    try:
        if incident.term:
            recompute_behaviour_summary(incident.student, incident.term)
    except Exception:
        pass


@receiver(post_save, sender=DisciplineConsequence)
def on_consequence_saved(sender, instance, created, **kwargs):
    """
    When a suspension consequence is created, ensure the incident
    is flagged as requiring principal approval.
    """
    if created and instance.consequence_type in ('suspension_internal', 'suspension_external', 'expulsion'):
        incident = instance.incident
        if not incident.requires_principal_approval:
            DisciplineIncident.objects.filter(pk=incident.pk).update(
                requires_principal_approval=True,
                status='awaiting_principal_approval',
            )
        # Mark consequence as requiring approval
        DisciplineConsequence.objects.filter(pk=instance.pk).update(
            requires_approval=True,
            approval_status='pending_approval',
        )


@receiver(post_save, sender=MeritRecord)
def on_merit_saved(sender, instance, created, **kwargs):
    """Rebuild behaviour summary when a merit is awarded."""
    try:
        if instance.term:
            recompute_behaviour_summary(instance.student, instance.term)
    except Exception:
        pass

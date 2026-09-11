# -*- coding: utf-8 -*-
"""
ASMS Visitor Management — Signals

Notifies the host staff member by SMS the moment a visitor checks in.
Mirrors the post_save signal pattern already used for the equivalent
event elsewhere in the project (e.g. attendance's absence notification) —
same shape: something happens, a Celery-backed notification fires off the
back of a model save, nothing in the view layer has to remember to call it.

Wired up via VisitorConfig.ready() in apps.py — Django never auto-imports
signals.py on its own.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.sms import send_sms

from .models import VisitorLog

logger = logging.getLogger("visitor.signals")


@receiver(post_save, sender=VisitorLog)
def notify_host_on_checkin(sender, instance, created, **kwargs):
    """
    Fires once, at check-in only (created=True) — NOT on every subsequent
    save(). VisitorLog.save() also runs on check-out (status flips to
    checked_out) and on the overstay task's status flip; without the
    `created` guard the host would get re-notified on both of those too.
    """
    if not created:
        return

    host = instance.host
    if host is None or not host.phone:
        # No specific staff host (e.g. a delivery/vendor visit), or the
        # host has no phone on file — nothing to send.
        return

    if not host.notify_sms:
        return

    visitor_name = instance.visitor.full_name
    purpose = instance.get_purpose_display()
    message = (
        f"Visitor at reception: {visitor_name} ({purpose}) is here to see you. "
        f"Badge {instance.badge_number}."
    )

    ok = send_sms(
        tenant=instance.tenant,
        phone=host.phone,
        message=message,
        idempotency_key=f"visitor-checkin-{instance.pk}",
    )
    if not ok:
        # send_sms() never raises and already logs the failure internally —
        # this second log line just makes it easy to grep visitor-specific
        # notification failures without wading through the shared SMS log.
        logger.warning(
            "Host notification failed for VisitorLog %s (host=%s)", instance.pk, host.pk
        )

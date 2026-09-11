"""
Signal handlers — the glue between model saves and Celery tasks, matching the same
pattern used elsewhere in the base spec (e.g. Appendix D.1: post_save on AttendanceRecord
fires send_absence_sms).
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import VehicleLocationPing, BoardingEvent
from . import tasks


@receiver(post_save, sender=VehicleLocationPing)
def on_location_ping_saved(sender, instance, created, **kwargs):
    if created:
        tasks.broadcast_location.delay(instance.id)


@receiver(post_save, sender=BoardingEvent)
def on_boarding_event_saved(sender, instance, created, **kwargs):
    if created:
        tasks.send_boarding_notification.delay(instance.id)

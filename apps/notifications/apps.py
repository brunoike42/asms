from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Must match the dotted path used in INSTALLED_APPS exactly.
    name = "apps.notifications"
    verbose_name = "Notifications (SMS)"

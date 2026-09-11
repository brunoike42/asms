from django.apps import AppConfig


class TransportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.transport"
    verbose_name = "Transport & Fleet Intelligence"

    def ready(self):
        # Registers the post_save signal handlers defined in signals.py
        from . import signals  # noqa: F401

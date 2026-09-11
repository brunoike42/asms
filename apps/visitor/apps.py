from django.apps import AppConfig
class VisitorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.visitor"
    verbose_name = "Visitor Management"

    def ready(self):
        from . import signals  # noqa: F401

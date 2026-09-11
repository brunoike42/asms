from django.apps import AppConfig
class HealthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.health"
    verbose_name = "Health & Medical"
    def ready(self):
        import apps.health.signals  # noqa: F401

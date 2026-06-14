from django.apps import AppConfig


class ParentPortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.parent_portal'
    verbose_name = 'Parent Portal'

    def ready(self):
        import apps.parent_portal.signals  # noqa — connects all platform signals

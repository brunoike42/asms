from django.apps import AppConfig


class DisciplineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.discipline'
    verbose_name = 'Discipline & Behaviour'

    def ready(self):
        import apps.discipline.signals  # noqa

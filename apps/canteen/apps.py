from django.apps import AppConfig
class CanteenConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.canteen'
    verbose_name = 'Canteen Management'
    def ready(self):
        import apps.canteen.signals  # noqa: F401

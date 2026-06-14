from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.payments'
    verbose_name = 'Online Payments (PesaPal)'

    def ready(self):
        import apps.payments.signals  # noqa

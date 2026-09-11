from django.apps import AppConfig


class PlatformBillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.platform_billing'
    verbose_name = 'Platform Billing & Subscriptions'

    def ready(self):
        from . import receivers  # noqa: F401 -- connects platform_payment_confirmed

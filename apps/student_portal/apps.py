# ═══════════════════════════════════════════════════
# student_portal/apps.py
# ═══════════════════════════════════════════════════
from django.apps import AppConfig


class StudentPortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name   = 'apps.student_portal'
    label  = 'student_portal'
    verbose_name = 'Student Portal'

    def ready(self):
        import apps.student_portal.signals  # noqa: F401

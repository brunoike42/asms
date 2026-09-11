# ============================================================
# FIX: apps/transport/apps.py
# ============================================================
#
# Change this line:
#     name = "transport"
#
# To this:
#     name = "apps.transport"
#
# Full corrected file:

from django.apps import AppConfig


class TransportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.transport"
    verbose_name = "Transport & Fleet Intelligence"

    def ready(self):
        # Registers the post_save signal handlers defined in signals.py
        from . import signals  # noqa: F401


# ============================================================
# ALSO CHECK: config/settings.py
# ============================================================
# Search INSTALLED_APPS for 'transport' — you may have it listed as both
# 'transport' AND 'apps.transport' by accident, or just 'transport' on its
# own (which would explain how the mismatched name above was even resolving
# at all). It should appear ONCE, as 'apps.transport', consistent with every
# other app entry (e.g. 'apps.attendance', 'apps.finance', 'apps.discipline').
#
# PowerShell one-liner to check quickly:
#   Select-String -Path .\config\settings.py -Pattern "transport"
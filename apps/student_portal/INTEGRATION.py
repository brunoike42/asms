# ASMS Student Portal — Integration Guide
# Phase 3 — Add to existing Django project

# ─────────────────────────────────────────────────────────
# 1. settings.py — add to INSTALLED_APPS
# ─────────────────────────────────────────────────────────
INSTALLED_APPS = [
    # ... existing Phase 1 & 2 apps ...
    'django.contrib.humanize',                   # ← add if not already present (used for number formatting, e.g. 250,000)
    'student_portal.apps.StudentPortalConfig',   # ← add this
]


# ─────────────────────────────────────────────────────────
# 2. urls.py (project root) — mount the portal
# ─────────────────────────────────────────────────────────
from django.urls import path, include

urlpatterns = [
    # ... existing url patterns ...
    path('portal/', include('student_portal.urls', namespace='student_portal')),  # ← add
]


# ─────────────────────────────────────────────────────────
# 3. Run migration
# ─────────────────────────────────────────────────────────
# python manage.py migrate student_portal


# ─────────────────────────────────────────────────────────
# 4. Verify signal connections (optional sanity check)
# ─────────────────────────────────────────────────────────
# python manage.py shell
# >>> from student_portal import signals
# >>> print("Signals loaded OK")


# ─────────────────────────────────────────────────────────
# 5. Seed clearance items for existing tenants (run once)
# ─────────────────────────────────────────────────────────
# python manage.py shell
# >>> from tenants.models import Tenant
# >>> from staff.models import Staff
# >>> from student_portal.models import AcademicClearanceItem
# >>>
# >>> DEFAULT_ITEMS = [
# ...     ('Library Clearance',     'library',   0),
# ...     ('Finance Clearance',     'finance',   1),
# ...     ('Academic Registrar',    'academics', 2),
# ...     ('ICT / Equipment',       'it',        3),
# ...     ('Sports / PE',           'sports',    4),
# ... ]
# >>> for tenant in Tenant.objects.all():
# ...     for name, dept, order in DEFAULT_ITEMS:
# ...         AcademicClearanceItem.objects.get_or_create(
# ...             tenant=tenant, name=name,
# ...             defaults={'department': dept, 'order': order}
# ...         )
# ...     print(f"Seeded clearance items for {tenant.name}")


# ─────────────────────────────────────────────────────────
# 6. Login redirect — send students to portal dashboard
#    Add to accounts/views.py get_dashboard_url()
# ─────────────────────────────────────────────────────────
# def get_dashboard_url(user):
#     ...
#     if hasattr(user, 'student'):
#         return reverse('student_portal:dashboard')
#     ...


# ─────────────────────────────────────────────────────────
# 7. Template directory — ensure templates are found
#    settings.py TEMPLATES[0]['DIRS']
# ─────────────────────────────────────────────────────────
# TEMPLATES = [{
#     ...
#     'APP_DIRS': True,   # ← must be True, or add student_portal/templates to DIRS
# }]

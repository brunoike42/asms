"""
Scans ALL app urls.py files, finds any view that's referenced but not defined,
and adds a clean stub view so the server starts without errors.

Run from your project root (where manage.py is):
  python fix_missing_views.py
"""
import os, re, ast, sys

ROOT = os.getcwd()
APPS_DIR = os.path.join(ROOT, 'apps')

ALL_APPS = [
    d for d in os.listdir(APPS_DIR)
    if os.path.isdir(os.path.join(APPS_DIR, d))
    and os.path.exists(os.path.join(APPS_DIR, d, 'urls.py'))
]

print("\n═══ ASMS — Missing Views Fixer ═══\n")
print(f"  Apps found: {', '.join(sorted(ALL_APPS))}\n")

STUB_TEMPLATE = '''
@login_required
def {name}(request):
    """Auto-generated stub — implement this view."""
    return render(request, 'core/coming_soon.html', {{
        'page_title': '{title}',
        'message': 'This feature is coming soon.',
    }})
'''

STUB_HEADER = """
# ── Auto-generated stub views (added by fix_missing_views.py) ─────────────
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
"""

fixed_apps = []

for app in sorted(ALL_APPS):
    app_dir = os.path.join(APPS_DIR, app)
    urls_path  = os.path.join(app_dir, 'urls.py')
    views_path = os.path.join(app_dir, 'views.py')

    if not os.path.exists(urls_path) or not os.path.exists(views_path):
        continue

    # ── Read views referenced in urls.py ──────────────────────────────
    with open(urls_path, encoding='utf-8') as f:
        urls_content = f.read()

    # Find all "views.something" references
    view_refs = re.findall(r'views\.(\w+)', urls_content)
    view_refs = sorted(set(view_refs))

    # ── Read views defined in views.py ────────────────────────────────
    with open(views_path, encoding='utf-8') as f:
        views_content = f.read()

    defined_views = set(re.findall(r'^(?:def|async def)\s+(\w+)', views_content, re.MULTILINE))

    # ── Find what's missing ────────────────────────────────────────────
    missing = [v for v in view_refs if v not in defined_views]

    if not missing:
        print(f"  ✓ {app:20s} — all views present")
        continue

    print(f"  ✗ {app:20s} — missing: {', '.join(missing)}")

    # ── Add stub views ─────────────────────────────────────────────────
    stubs = []
    # Add header once if not present
    if 'Auto-generated stub views' not in views_content:
        # Make sure login_required is imported
        if 'login_required' not in views_content:
            stubs.append(STUB_HEADER)

    for view_name in missing:
        title = view_name.replace('_', ' ').title()
        stubs.append(STUB_TEMPLATE.format(name=view_name, title=title))

    if stubs:
        with open(views_path, 'a', encoding='utf-8') as f:
            f.write('\n'.join(stubs))
        print(f"    → Added {len(missing)} stub(s) to apps/{app}/views.py")
        fixed_apps.append(app)

# ── Create the coming_soon template if it doesn't exist ─────────────────
templates_dir = os.path.join(ROOT, 'templates', 'core')
os.makedirs(templates_dir, exist_ok=True)
coming_soon = os.path.join(templates_dir, 'coming_soon.html')

if not os.path.exists(coming_soon):
    with open(coming_soon, 'w', encoding='utf-8') as f:
        f.write("""{% extends "base.html" %}
{% block title %}{{ page_title }}{% endblock %}
{% block page_title %}{{ page_title }}{% endblock %}
{% block content %}
<div class="card">
  <div class="card-body text-center py-5">
    <i class="bi bi-tools fs-1 text-warning d-block mb-3"></i>
    <h4 class="fw-bold">{{ page_title }}</h4>
    <p class="text-muted">{{ message|default:"This feature is under construction." }}</p>
    <a href="javascript:history.back()" class="btn btn-outline-secondary mt-2">
      <i class="bi bi-arrow-left me-1"></i>Go Back
    </a>
  </div>
</div>
{% endblock %}
""")
    print(f"\n  ✓ Created templates/core/coming_soon.html")

# ── Also check config/urls.py for Phase 2 includes ──────────────────────
config_urls = os.path.join(ROOT, 'config', 'urls.py')
if os.path.exists(config_urls):
    with open(config_urls, encoding='utf-8') as f:
        config_content = f.read()

    phase2_apps = {
        'academics':   "path('academics/',   include('apps.academics.urls')),",
        'exams':       "path('exams/',       include('apps.exams.urls')),",
        'staff_hr':    "path('staff/',       include('apps.staff_hr.urls')),",
        'library':     "path('library/',     include('apps.library.urls')),",
        'lms':         "path('lms/',         include('apps.lms.urls')),",
        'assignments': "path('assignments/', include('apps.assignments.urls')),",
    }

    missing_includes = []
    for app, line in phase2_apps.items():
        app_key = f"apps.{app}"
        if app_key not in config_content:
            missing_includes.append(line)

    if missing_includes:
        print(f"\n  ⚠ These Phase 2 URL includes are missing from config/urls.py:")
        for line in missing_includes:
            print(f"    {line}")
        print(f"\n  Add them inside the urlpatterns = [ ... ] list in config/urls.py")
    else:
        print(f"\n  ✓ config/urls.py already has Phase 2 includes")
else:
    print(f"\n  ⚠ Could not find config/urls.py — your main urls file may be elsewhere")
    print(f"     Check where your ROOT_URLCONF points in settings.py")

print(f"\n═══════════════════════════════════════════════════════════")
if fixed_apps:
    print(f"  Fixed {len(fixed_apps)} app(s): {', '.join(fixed_apps)}")
print(f"  NOW RUN:")
print(f"    python manage.py makemigrations")
print(f"    python manage.py migrate")
print(f"═══════════════════════════════════════════════════════════\n")
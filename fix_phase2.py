"""
Run this from your Phase 1 project root (where manage.py is).
It moves the Phase 2 apps into your apps/ folder and fixes all imports.

Usage:
  cd E:\DJANGO\ASMS\asms
  python fix_phase2.py
"""
import os, shutil, re, sys

ROOT = os.getcwd()
APPS_DIR = os.path.join(ROOT, 'apps')
NEW_APPS = ['academics', 'exams', 'staff_hr', 'library', 'lms', 'assignments']

print("\n═══ ASMS Phase 2 — Auto-Fix Script ═══\n")

# ── 1. Check apps/ folder exists ────────────────────────────────────────
if not os.path.isdir(APPS_DIR):
    print("✗ No 'apps/' folder found in this directory.")
    print("  Make sure you are running this from your Phase 1 root.")
    sys.exit(1)
print(f"✓ Found apps/ folder: {APPS_DIR}")

# ── 2. Move each new app INTO apps/ ─────────────────────────────────────
for app in NEW_APPS:
    src = os.path.join(ROOT, app)
    dst = os.path.join(APPS_DIR, app)
    if os.path.isdir(src) and not os.path.isdir(dst):
        shutil.move(src, dst)
        print(f"✓ Moved {app}/ → apps/{app}/")
    elif os.path.isdir(dst):
        print(f"  Already in apps/{app}/ — skipping move")
    else:
        print(f"✗ Could not find {app}/ in root — did you copy it?")

# ── 3. Fix apps.py in each new app ──────────────────────────────────────
for app in NEW_APPS:
    apps_py = os.path.join(APPS_DIR, app, 'apps.py')
    if os.path.exists(apps_py):
        with open(apps_py) as f:
            content = f.read()
        # Fix name = 'academics' → name = 'apps.academics'
        fixed = re.sub(
            rf"name\s*=\s*['\"]({app})['\"]",
            f"name = 'apps.{app}'",
            content
        )
        with open(apps_py, 'w') as f:
            f.write(fixed)
        print(f"✓ Fixed apps/{app}/apps.py  (name = 'apps.{app}')")

# ── 4. Fix all import statements inside the new apps ────────────────────
# e.g. "from core.models" → "from apps.core.models"
# e.g. "from students.models" → "from apps.students.models"
phase1_apps = ['core', 'students', 'admissions', 'attendance',
               'finance', 'communication']
all_apps = phase1_apps + NEW_APPS

def fix_imports(filepath):
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    changed = False
    for app_name in all_apps:
        # Match "from app_name.xxx" but NOT "from apps.app_name.xxx" already
        pattern = rf'(?<!apps\.)(\bfrom\s+)({app_name})(\.\w)'
        replacement = rf'\1apps.\2\3'
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            content = new_content
            changed = True
    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    return changed

fixed_files = 0
for app in NEW_APPS:
    app_path = os.path.join(APPS_DIR, app)
    for fname in ['models.py', 'views.py', 'urls.py', 'admin.py']:
        fpath = os.path.join(app_path, fname)
        if os.path.exists(fpath):
            if fix_imports(fpath):
                print(f"✓ Fixed imports in apps/{app}/{fname}")
                fixed_files += 1

print(f"\n✓ Fixed imports in {fixed_files} files")

# ── 5. Print what to add to settings.py ─────────────────────────────────
print("\n═══════════════════════════════════════════════════════════")
print("  NOW DO THIS MANUALLY — add to your INSTALLED_APPS:")
print("═══════════════════════════════════════════════════════════")
print("""
    'apps.academics',
    'apps.exams',
    'apps.staff_hr',
    'apps.library',
    'apps.lms',
    'apps.assignments',
""")
print("═══════════════════════════════════════════════════════════")
print("  AND add to your main urls.py urlpatterns:")
print("═══════════════════════════════════════════════════════════")
print("""
    path('academics/',   include('apps.academics.urls')),
    path('exams/',       include('apps.exams.urls')),
    path('staff/',       include('apps.staff_hr.urls')),
    path('library/',     include('apps.library.urls')),
    path('lms/',         include('apps.lms.urls')),
    path('assignments/', include('apps.assignments.urls')),
""")
print("═══════════════════════════════════════════════════════════")
print("  THEN RUN:")
print("    python manage.py makemigrations")
print("    python manage.py migrate")
print("═══════════════════════════════════════════════════════════\n")
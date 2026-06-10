"""
Fixes the include() paths in config/urls.py for all Phase 2 apps.
Run from your project root:  python fix_config_urls.py
"""
import os, re

ROOT = os.getcwd()
urls_path = os.path.join(ROOT, 'config', 'urls.py')

if not os.path.exists(urls_path):
    print(f"✗ Cannot find config/urls.py at {urls_path}")
    raise SystemExit(1)

with open(urls_path, encoding='utf-8') as f:
    content = f.read()

original = content

# Fix every Phase 2 include that is missing the 'apps.' prefix
# Matches include('academics.urls') but NOT include('apps.academics.urls')
phase2_apps = ['academics', 'exams', 'staff_hr', 'library', 'lms', 'assignments']

for app in phase2_apps:
    # Replace include('academics.urls') → include('apps.academics.urls')
    # Also handles double-quoted strings and namespace variants
    pattern = rf"include\(['\"](?!apps\.){re.escape(app)}\.urls['\"]"
    fixed   = f"include('apps.{app}.urls'"

    new_content = re.sub(pattern, fixed, content)
    if new_content != content:
        print(f"  ✓ Fixed: include('{app}.urls') → include('apps.{app}.urls')")
        content = new_content
    else:
        # Check if it's already correct
        if f"apps.{app}.urls" in content:
            print(f"  ✓ Already correct: apps.{app}.urls")
        else:
            print(f"  ⚠ '{app}' not found in config/urls.py — add it manually (see below)")

if content != original:
    with open(urls_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\n  ✓ Saved config/urls.py")
else:
    print(f"\n  No changes made.")

# Show the user the correct lines to have in config/urls.py
print("""
═══════════════════════════════════════════════════════════
  Your config/urls.py Phase 2 lines should look like this:
═══════════════════════════════════════════════════════════

    path('academics/',   include('apps.academics.urls')),
    path('exams/',       include('apps.exams.urls')),
    path('staff/',       include('apps.staff_hr.urls')),
    path('library/',     include('apps.library.urls')),
    path('lms/',         include('apps.lms.urls')),
    path('assignments/', include('apps.assignments.urls')),

  NOT like this (missing apps. prefix):
    path('academics/',   include('academics.urls')),   ← WRONG

═══════════════════════════════════════════════════════════
  NOW RUN:
    python manage.py makemigrations
    python manage.py migrate
═══════════════════════════════════════════════════════════
""")
"""
Fixes ForeignKey user references in all Phase 2 models.py files.
Changes the broken string 'settings.AUTH_USER_MODEL' to the correct
Python variable settings.AUTH_USER_MODEL (no quotes).

Run from project root: python fix_fk_user.py
"""
import os, re

ROOT   = os.getcwd()
APPS   = os.path.join(ROOT, 'apps')
P2     = ['academics', 'exams', 'staff_hr', 'library', 'lms', 'assignments']

# Find the real AUTH_USER_MODEL value from settings
auth_user_model = None
for cfg in ['config', 'asms', 'settings']:
    for fname in ['settings.py', 'base.py']:
        sp = os.path.join(ROOT, cfg, fname)
        if os.path.exists(sp):
            with open(sp, encoding='utf-8') as f:
                sc = f.read()
            m = re.search(r"AUTH_USER_MODEL\s*=\s*['\"](.+?)['\"]", sc)
            if m:
                auth_user_model = m.group(1)
                print(f"  Found AUTH_USER_MODEL = '{auth_user_model}'  (in {sp})")
                break

print(f"\n  Will use: settings.AUTH_USER_MODEL  →  resolves to '{auth_user_model}'\n")

for app in P2:
    path = os.path.join(APPS, app, 'models.py')
    if not os.path.exists(path):
        continue

    with open(path, encoding='utf-8') as f:
        content = f.read()

    original = content

    # Fix 1: ForeignKey('settings.AUTH_USER_MODEL'  → ForeignKey(settings.AUTH_USER_MODEL
    content = re.sub(
        r"""ForeignKey\(['"]{1,2}settings\.AUTH_USER_MODEL['"]{1,2}""",
        "ForeignKey(settings.AUTH_USER_MODEL",
        content
    )
    # Fix 2: OneToOneField('settings.AUTH_USER_MODEL'  → OneToOneField(settings.AUTH_USER_MODEL
    content = re.sub(
        r"""OneToOneField\(['"]{1,2}settings\.AUTH_USER_MODEL['"]{1,2}""",
        "OneToOneField(settings.AUTH_USER_MODEL",
        content
    )
    # Fix 3: Also handle lowercase variant settings.auth_user_model
    content = re.sub(
        r"""ForeignKey\(['"]{1,2}settings\.auth_user_model['"]{1,2}""",
        "ForeignKey(settings.AUTH_USER_MODEL",
        content
    )
    content = re.sub(
        r"""OneToOneField\(['"]{1,2}settings\.auth_user_model['"]{1,2}""",
        "OneToOneField(settings.AUTH_USER_MODEL",
        content
    )

    # Ensure 'from django.conf import settings' is at the top
    if 'settings.AUTH_USER_MODEL' in content:
        if 'from django.conf import settings' not in content:
            # Add after the first import line
            content = re.sub(
                r'^(from django\.db import models.*?\n)',
                r'\1from django.conf import settings\n',
                content,
                count=1,
                flags=re.MULTILINE
            )
            # If that didn't work, prepend it
            if 'from django.conf import settings' not in content:
                content = "from django.conf import settings\n" + content

    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ Fixed apps/{app}/models.py")
    else:
        print(f"  — No changes needed: apps/{app}/models.py")

print("""
═══════════════════════════════════════════════════════════
  NOW RUN:
    python manage.py makemigrations
    python manage.py migrate
═══════════════════════════════════════════════════════════
""")
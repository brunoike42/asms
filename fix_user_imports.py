"""
Fixes all Phase 2 apps that import User from core.models.
Replaces them with Django's get_user_model() — works with any User location.

Run from your project root:  python fix_user_imports.py
"""
import os, re

ROOT    = os.getcwd()
APPS    = os.path.join(ROOT, 'apps')
P2_APPS = ['academics', 'exams', 'staff_hr', 'library', 'lms', 'assignments']
FILES   = ['models.py', 'views.py', 'admin.py', 'urls.py']

print("\n═══ Fixing User imports in Phase 2 apps ═══\n")

# ── First: find where User actually is in Phase 1 ───────────────────────
user_location = "django.contrib.auth.models"  # default assumption
settings_path = None

# Search settings.py for AUTH_USER_MODEL
for cfg_dir in ['config', 'asms', 'settings']:
    for fname in ['settings.py', 'base.py']:
        sp = os.path.join(ROOT, cfg_dir, fname)
        if os.path.exists(sp):
            with open(sp, encoding='utf-8') as f:
                sc = f.read()
            m = re.search(r"AUTH_USER_MODEL\s*=\s*['\"](.+?)['\"]", sc)
            if m:
                user_location = m.group(1)
                settings_path = sp
                break

print(f"  AUTH_USER_MODEL found: '{user_location}'  (from {settings_path or 'not found — using default'})")

# ── Fix each Phase 2 app file ────────────────────────────────────────────
total_fixed = 0

for app in P2_APPS:
    for fname in FILES:
        fpath = os.path.join(APPS, app, fname)
        if not os.path.exists(fpath):
            continue

        with open(fpath, encoding='utf-8') as f:
            content = f.read()

        original = content
        changed  = False

        # Pattern 1: from apps.core.models import ..., User, ...
        # Remove User from the import and add get_user_model separately
        def fix_core_import(m):
            imports = [i.strip() for i in m.group(1).split(',')]
            non_user = [i for i in imports if i != 'User']
            result = ''
            if non_user:
                result += f"from apps.core.models import {', '.join(non_user)}\n"
            result += "from django.contrib.auth import get_user_model\nUser = get_user_model()"
            return result

        new = re.sub(
            r'from apps\.core\.models import ([\w\s,]+\bUser\b[\w\s,]*)',
            fix_core_import,
            content
        )
        if new != content:
            content = new
            changed = True

        # Pattern 2: standalone import of just User
        new = re.sub(
            r'from apps\.core\.models import User\b',
            'from django.contrib.auth import get_user_model\nUser = get_user_model()',
            content
        )
        if new != content:
            content = new
            changed = True

        # Pattern 3: any remaining "from X import ..., User" from other locations
        new = re.sub(
            r'from (?:apps\.)?(?:core|accounts|users)\.models import ([^;\n]*\bUser\b[^;\n]*)',
            lambda m: fix_core_import(m) if 'User' in m.group(1) else m.group(0),
            content
        )
        if new != content:
            content = new
            changed = True

        # Clean duplicate get_user_model imports
        lines = content.split('\n')
        seen_getuser = False
        seen_user_eq = False
        cleaned = []
        for line in lines:
            if 'from django.contrib.auth import get_user_model' in line:
                if seen_getuser:
                    continue
                seen_getuser = True
            if re.match(r'^User\s*=\s*get_user_model\(\)', line.strip()):
                if seen_user_eq:
                    continue
                seen_user_eq = True
            cleaned.append(line)
        content = '\n'.join(cleaned)

        if content != original:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ Fixed apps/{app}/{fname}")
            total_fixed += 1

# ── Fix ForeignKey references to User in models.py ───────────────────────
# In models.py, ForeignKeys to User should use settings.AUTH_USER_MODEL string
for app in P2_APPS:
    mpath = os.path.join(APPS, app, 'models.py')
    if not os.path.exists(mpath):
        continue
    with open(mpath, encoding='utf-8') as f:
        content = f.read()
    original = content

    # Add settings import if needed and not present
    if (f"'{user_location}'" not in content and
        'AUTH_USER_MODEL' not in content and
        re.search(r"ForeignKey\(User", content)):
        # Replace ForeignKey(User, with ForeignKey(settings.AUTH_USER_MODEL,
        if 'from django.conf import settings' not in content:
            content = "from django.conf import settings\n" + content
        content = re.sub(
            r"ForeignKey\(User\b",
            f"ForeignKey(settings.AUTH_USER_MODEL",
            content
        )
        content = re.sub(
            r"OneToOneField\(User\b",
            f"OneToOneField(settings.AUTH_USER_MODEL",
            content
        )
        if content != original:
            with open(mpath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ Fixed ForeignKey(User) → ForeignKey(AUTH_USER_MODEL) in apps/{app}/models.py")
            total_fixed += 1

print(f"\n  Fixed {total_fixed} file(s)")
print("""
═══════════════════════════════════════════════════════════
  NOW RUN:
    python manage.py makemigrations
    python manage.py migrate
═══════════════════════════════════════════════════════════
""")
"""
fix_context_name.py
====================
Django ImportError: "parent_context" attribute not found.

settings.py already has:
    'apps.parent_portal.context_processors.parent_context'

But context_processors.py defines  parent_students  (wrong name).
This script rewrites the file with the correct function name.

Run from the project root:
    python fix_context_name.py
"""
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CP_PATH = os.path.join(BASE_DIR, "apps", "parent_portal", "context_processors.py")

CODE = '''\
"""
apps/parent_portal/context_processors.py
Injects `students` and `active_student` into every parent-portal template.
Referenced in settings.py as:
    apps.parent_portal.context_processors.parent_context
"""


def parent_context(request):
    """
    Makes `students` and `active_student` available in all templates
    that extend parent/base.html, bridging the old children_data
    convention with the new sidebar variables.
    """
    if not request.user.is_authenticated:
        return {}

    if not request.path.startswith("/parent"):
        return {}

    try:
        profile = getattr(request.user, "parent_profile", None)
        if profile is None:
            return {"students": [], "active_student": None}

        students = []
        if hasattr(profile, "children"):
            students = list(profile.children.all())
        elif hasattr(profile, "students"):
            students = list(profile.students.all())

        active_student = students[0] if students else None

        # Honour ?child_id= switcher chip
        child_id = (
            request.GET.get("child_id")
            or request.session.get("active_child_id")
        )
        if child_id:
            for s in students:
                if str(s.pk) == str(child_id):
                    active_student = s
                    request.session["active_child_id"] = str(child_id)
                    break

        return {
            "students": students,
            "active_student": active_student,
        }
    except Exception:
        return {"students": [], "active_student": None}


# Alias kept for any legacy references
parent_students = parent_context
'''

os.makedirs(os.path.dirname(CP_PATH), exist_ok=True)
with open(CP_PATH, "w", encoding="utf-8") as f:
    f.write(CODE)

print(f"[OK] Rewritten: {CP_PATH}")
print()

# Also verify settings.py has it registered (don't add duplicate)
settings_candidates = [
    "core/settings.py",
    "settings.py",
    "config/settings.py",
    "asms/settings.py",
]
for rel in settings_candidates:
    p = os.path.join(BASE_DIR, rel)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
        if "parent_context" in content:
            print(f"[OK] settings.py ({rel}) already references parent_context — no change needed.")
        else:
            print(f"[WARN] parent_context not found in {rel} — add this line manually:")
            print("       'apps.parent_portal.context_processors.parent_context',")
        break

print()
print("Now run:")
print("  python manage.py runserver")
print("Then hard-refresh /parent/ with Ctrl+Shift+R")
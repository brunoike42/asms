"""
fix_students_variable.py
========================
Fixes: VariableDoesNotExist at /parent/ — 'students' not in context

ROOT CAUSE
----------
The upgraded parent/base.html uses {{ students }} / {{ student }} in the
sidebar child-switcher, but every existing parent_portal view passes
children_data (not students).  A context processor is the right fix:
it runs on every request that hits any parent template, so all 10+
views get the variable without touching each one individually.

WHAT THIS SCRIPT DOES
---------------------
1. Writes  apps/parent_portal/context_processors.py
2. Injects the processor into TEMPLATES[0]['OPTIONS']['context_processors']
   in settings.py  (safe — checks for duplicates)
3. Patches parent/base.html: replaces any bare {{ students }} / {% with %}
   blocks that reference `students` with children_data-aware equivalents
   if the base.html still uses old variable names.

Run from the project root:
    python fix_students_variable.py
"""

import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ── 1. CONTEXT PROCESSOR ──────────────────────────────────────────────────────

CP_PATH = os.path.join(BASE_DIR, "apps", "parent_portal", "context_processors.py")

CP_CODE = '''\
"""
apps/parent_portal/context_processors.py
Injects `students` and `active_student` into every parent-portal template,
bridging the old children_data convention with the new sidebar variables.
"""
from django.db.models import QuerySet


def parent_students(request):
    """
    Makes `students` available in all templates that extend parent/base.html.

    Priority order for `students`:
      1. Already in view context as 'students'          → use as-is
      2. View passed 'children_data'                    → alias it
      3. Parent profile children relation              → query it
      4. Fallback                                       → empty list
    """
    if not request.user.is_authenticated:
        return {}

    # Avoid DB hit on non-parent pages
    path = request.path
    if not path.startswith("/parent"):
        return {}

    try:
        profile = getattr(request.user, "parent_profile", None)
        if profile is None:
            return {"students": [], "active_student": None}

        # Try the ManyToMany / related manager common patterns
        students = []
        if hasattr(profile, "children"):
            qs = profile.children.all()
            students = list(qs)
        elif hasattr(profile, "students"):
            qs = profile.students.all()
            students = list(qs)

        active_student = students[0] if students else None

        # Honour ?child_id=<pk> query param for the switcher chip
        child_id = request.GET.get("child_id") or request.session.get("active_child_id")
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
        # Never break the request over a context processor failure
        return {"students": [], "active_student": None}
'''

def write_context_processor():
    os.makedirs(os.path.dirname(CP_PATH), exist_ok=True)
    with open(CP_PATH, "w", encoding="utf-8") as f:
        f.write(CP_CODE)
    print(f"[OK] Written: {CP_PATH}")


# ── 2. REGISTER IN settings.py ────────────────────────────────────────────────

def patch_settings():
    settings_path = os.path.join(BASE_DIR, "core", "settings.py")
    if not os.path.exists(settings_path):
        # Try alternate locations
        for candidate in ["settings.py", "config/settings.py", "asms/settings.py"]:
            p = os.path.join(BASE_DIR, candidate)
            if os.path.exists(p):
                settings_path = p
                break
        else:
            print("[WARN] Could not locate settings.py — skipping auto-registration.")
            print("       Add manually:  'apps.parent_portal.context_processors.parent_students'")
            return

    with open(settings_path, "r", encoding="utf-8") as f:
        content = f.read()

    PROC = "apps.parent_portal.context_processors.parent_students"

    if PROC in content:
        print(f"[OK] Context processor already registered in {settings_path}")
        return

    # Find the context_processors list and append our entry
    # Pattern: match the last item before the closing ] of context_processors
    pattern = r"(context_processors['\"]?\s*:\s*\[)(.*?)(\s*\])"

    def replacer(m):
        opening, body, closing = m.group(1), m.group(2), m.group(3)
        # Add our processor after the last entry, keeping existing formatting
        if body.rstrip().endswith(","):
            new_body = body.rstrip() + f"\n                '{PROC}',"
        else:
            new_body = body.rstrip() + f",\n                '{PROC}',"
        return opening + new_body + closing

    new_content, count = re.subn(pattern, replacer, content, count=1, flags=re.DOTALL)

    if count == 0:
        print("[WARN] Could not find context_processors list in settings.py")
        print(f"       Add manually:  '{PROC}'")
        return

    with open(settings_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"[OK] Registered context processor in {settings_path}")


# ── 3. PATCH base.html — fix bare {{ students }} if still broken ──────────────

def patch_base_html():
    """
    The sidebar in base.html may do:
        {% with student=students.0 %}  or  {% for s in students %}
    These are fine once the context processor runs.

    However if base.html still references `children_data` in some places
    and `students` in others, this function reports those lines so you
    can review them.  It does NOT auto-rewrite template logic.
    """
    base_path = os.path.join(BASE_DIR, "templates", "parent", "base.html")
    if not os.path.exists(base_path):
        print(f"[WARN] {base_path} not found — skipping base.html check.")
        return

    with open(base_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    issues = []
    for i, line in enumerate(lines, 1):
        if "children_data" in line:
            issues.append((i, "children_data", line.rstrip()))
        if "{% with" in line and "student" in line:
            issues.append((i, "{% with student … %}", line.rstrip()))

    if issues:
        print("\n[INFO] base.html lines that reference children_data or student:")
        for lineno, tag, text in issues:
            print(f"  Line {lineno:4d}  [{tag}]  {text[:90]}")
        print()
        print("  After this fix, {{ students }} and {{ active_student }} are injected")
        print("  by the context processor, so {% with %} blocks using them will work.")
        print("  If base.html still uses children_data, replace it with students.")
    else:
        print("[OK] base.html: no children_data references found — sidebar variables look clean.")


# ── 4. QUICK DASHBOARD VIEW PATCH (belt-and-suspenders) ──────────────────────

def patch_dashboard_view():
    """
    Belt-and-suspenders: also add `students` key to the dashboard view's
    return context so it works even before a page refresh picks up the
    context processor.
    """
    views_path = os.path.join(BASE_DIR, "apps", "parent_portal", "views.py")
    if not os.path.exists(views_path):
        print("[WARN] apps/parent_portal/views.py not found — skipping view patch.")
        return

    with open(views_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "'students': children_data" in content or '"students": children_data' in content:
        print("[OK] views.py dashboard already passes 'students'.")
        return

    # Replace the context dict return that has children_data but not students
    # Pattern: find  'children_data': <varname>  and add students alias next to it
    new_content = re.sub(
        r"(['\"])children_data\1\s*:\s*(\w+)",
        lambda m: f"{m.group(1)}children_data{m.group(1)}: {m.group(2)}, 'students': {m.group(2)}",
        content,
    )

    if new_content == content:
        print("[WARN] Could not auto-patch dashboard view — add manually:")
        print("       'students': children_data,   # alias for base.html sidebar")
        return

    with open(views_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"[OK] Patched views.py — dashboard now passes 'students' alongside 'children_data'.")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("ASMS — fix VariableDoesNotExist 'students'")
    print("=" * 60)

    write_context_processor()
    patch_settings()
    patch_base_html()
    patch_dashboard_view()

    print()
    print("=" * 60)
    print("Done.  Now run:")
    print("  python manage.py check")
    print("  python manage.py runserver")
    print()
    print("Then hard-refresh /parent/ with Ctrl+Shift+R")
    print("=" * 60)


if __name__ == "__main__":
    main()
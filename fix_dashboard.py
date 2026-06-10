#!/usr/bin/env python3
"""
Two things this script does:
  1. Fixes the two broken role dashboards (/dashboard/finance/ and /dashboard/teacher/)
  2. Makes the sidebar role-aware — each role only sees sections relevant to their job

Run from E:\\DJANGO\\ASMS\\asms\\:  python fix_dashboards_and_sidebar.py
"""
import os, re

BASE = r"E:\DJANGO\ASMS\asms"

def w(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✓  {os.path.relpath(path, BASE)}")

def patch(path, old, new, label):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if old in src:
        with open(path, "w", encoding="utf-8") as f:
            f.write(src.replace(old, new))
        print(f"  ✓  {label}")
    else:
        print(f"  ⚠  {label} — pattern not found, may already be fixed")


# ══════════════════════════════════════════════════════════════════════════════
#  FIX 1 — finance_dashboard: paid_amount → amount_paid
# ══════════════════════════════════════════════════════════════════════════════
patch(
    os.path.join(BASE, "apps", "core", "views.py"),
    "'paid_amount'",
    "'amount_paid'",
    "apps/core/views.py — paid_amount → amount_paid"
)

# ══════════════════════════════════════════════════════════════════════════════
#  FIX 2 — teacher dashboard: attendance:mark → attendance:home
#  (mark requires a classroom_pk arg; home is the safe landing page)
# ══════════════════════════════════════════════════════════════════════════════
patch(
    os.path.join(BASE, "templates", "dashboard", "teacher.html"),
    "attendance:mark",
    "attendance:home",
    "templates/dashboard/teacher.html — attendance:mark → attendance:home"
)


# ══════════════════════════════════════════════════════════════════════════════
#  CREATE context processor — injects role flags into every template
# ══════════════════════════════════════════════════════════════════════════════
ctx_path = os.path.join(BASE, "apps", "core", "context_processors.py")

w(ctx_path, """\
\"\"\"
Role-based context flags injected into every template.
Use these in base.html to show/hide sidebar sections per role.

Usage in templates:
  {% if can_see_finance %} ... {% endif %}
  {% if is_full_admin %}   ... {% endif %}
\"\"\"

ADMIN_ROLES = (
    "school_admin",
    "principal",
    "platform_admin",
    "network_admin",
)


def role_context(request):
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {}

    role = getattr(request.user, "role", "")

    return {
        # Is this user a school administrator / platform owner?
        "is_full_admin": role in ADMIN_ROLES,

        # Which sidebar sections can this role see?
        "can_see_students": role in ADMIN_ROLES + (
            "teacher", "receptionist", "counsellor", "nurse",
        ),
        "can_see_academics": role in ADMIN_ROLES + ("teacher",),
        "can_see_finance":   role in ADMIN_ROLES + ("accountant",),
        "can_see_welfare":   role in ADMIN_ROLES + ("counsellor", "teacher"),
        "can_see_communication": role in ADMIN_ROLES + ("receptionist",),
        "can_see_staff":     role in ADMIN_ROLES,
        "can_see_library":   role in ADMIN_ROLES + ("librarian",),

        # Shorthand for staff + library (used for the combined sidebar section)
        "can_see_staff_or_library": role in ADMIN_ROLES + ("librarian",),
    }
""")


# ══════════════════════════════════════════════════════════════════════════════
#  PATCH settings.py — add context processor to TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════
settings_path = os.path.join(BASE, "config", "settings.py")
with open(settings_path, encoding="utf-8") as f:
    src = f.read()

CP = "apps.core.context_processors.role_context"
if CP not in src:
    # Insert after the last built-in context processor
    old = "django.template.context_processors.request',"
    new = "django.template.context_processors.request',\n                'apps.core.context_processors.role_context',"
    if old in src:
        src = src.replace(old, new)
        with open(settings_path, "w", encoding="utf-8") as f:
            f.write(src)
        print("  ✓  config/settings.py — role_context processor added")
    else:
        print("  ⚠  settings.py — add manually to TEMPLATES[0]['OPTIONS']['context_processors']:")
        print(f"        '{CP}',")
else:
    print("  ·  settings.py already has role_context processor")


# ══════════════════════════════════════════════════════════════════════════════
#  PATCH base.html — wrap each sidebar section with role conditions
# ══════════════════════════════════════════════════════════════════════════════
#
#  Strategy: split the nav innerHTML by nav-section-label divs,
#  then prepend {% if CONDITION %} / append {% endif %} around each
#  section that should be restricted.
#
#  Sections and their conditions:
#    Main                 → everyone       (no wrapping)
#    Students             → can_see_students
#    Academics            → can_see_academics
#    Learning             → can_see_academics   (Phase 2 added this)
#    Finance              → can_see_finance
#    Welfare & Discipline → can_see_welfare
#    Communication        → can_see_communication
#    Account              → everyone       (no wrapping)
#    Staff & Library      → can_see_staff_or_library
#    Staff                → can_see_staff
#    Library              → can_see_library
# ──────────────────────────────────────────────────────────────────────────────
SECTION_CONDITIONS = {
    "main":                       None,
    "students":                   "can_see_students",
    "academics":                  "can_see_academics",
    "learning":                   "can_see_academics",
    "finance":                    "can_see_finance",
    "welfare &amp; discipline":   "can_see_welfare",
    "welfare & discipline":       "can_see_welfare",
    "welfare":                    "can_see_welfare",
    "communication":              "can_see_communication",
    "account":                    None,
    "staff &amp; library":        "can_see_staff_or_library",
    "staff & library":            "can_see_staff_or_library",
    "staff":                      "can_see_staff",
    "library":                    "can_see_library",
}

base_path = os.path.join(BASE, "templates", "base", "base.html")
with open(base_path, encoding="utf-8") as f:
    html = f.read()

# Check if already patched
if "can_see_students" in html:
    print("  ·  base.html sidebar already has role conditions")
else:
    # Find the nav element content
    nav_match = re.search(r'(<nav[^>]*id=["\']sidebar["\'][^>]*>)(.*?)(</nav>)',
                          html, re.DOTALL)
    if not nav_match:
        print("  ⚠  base.html — could not find <nav id='sidebar'>")
        print("     Wrap sections manually using the conditions above.")
    else:
        nav_open    = nav_match.group(1)
        nav_content = nav_match.group(2)
        nav_close   = nav_match.group(3)

        # Split content by nav-section-label boundaries
        label_pat = re.compile(r'(?=\s*<div\s+class=["\']nav-section-label["\']>)',
                               re.IGNORECASE)
        parts = label_pat.split(nav_content)

        new_parts = []
        for part in parts:
            # Extract the section title from this part
            title_m = re.match(
                r'\s*<div\s+class=["\']nav-section-label["\']>(.*?)</div>',
                part, re.IGNORECASE
            )
            if title_m:
                raw_title = title_m.group(1).strip()
                key       = raw_title.lower()
                condition = SECTION_CONDITIONS.get(key)

                if condition:
                    # Wrap this section
                    new_parts.append(
                        f"\n      {{% if {condition} %}}"
                        f"{part}"
                        f"      {{% endif %}}\n"
                    )
                else:
                    new_parts.append(part)
            else:
                new_parts.append(part)

        new_nav = nav_open + "".join(new_parts) + nav_close
        html = html[:nav_match.start()] + new_nav + html[nav_match.end():]

        with open(base_path, "w", encoding="utf-8") as f:
            f.write(html)
        print("  ✓  base.html sidebar — role-based conditions added to all sections")


# ══════════════════════════════════════════════════════════════════════════════
#  DONE
# ══════════════════════════════════════════════════════════════════════════════
print("""
╔══════════════════════════════════════════════════════════════╗
║  Dashboard fixes + Role-aware sidebar done                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  What each role now sees in the sidebar:                    ║
║                                                              ║
║  school_admin / principal / platform_admin                   ║
║    → All sections (full access)                             ║
║                                                              ║
║  teacher                                                     ║
║    → Main, Students, Academics, Welfare & Discipline        ║
║    → NOT Finance, NOT Staff admin, NOT Admissions           ║
║                                                              ║
║  accountant                                                  ║
║    → Main, Finance, Account only                            ║
║                                                              ║
║  counsellor                                                  ║
║    → Main, Students, Welfare & Discipline, Account          ║
║                                                              ║
║  librarian                                                   ║
║    → Main, Staff & Library, Account                         ║
║                                                              ║
║  receptionist                                                ║
║    → Main, Students, Communication, Account                 ║
║                                                              ║
║  Test by logging in as different role accounts.             ║
║  Restart the dev server first: Ctrl+C then python manage.py runserver ║
╚══════════════════════════════════════════════════════════════╝
""")
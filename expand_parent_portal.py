"""
expand_parent_portal_phase3.py
==============================
Comprehensive Phase 3 Parent Portal expansion.

WHAT THIS SCRIPT DOES
---------------------
1.  DIAGNOSE  — shows exactly which URLs/views/templates exist vs. are missing
2.  STUDENT   — prints the shell one-liner to link a test student
3.  SIDEBAR   — adds Library, Timetable, Canteen, Health, Transport sections
                to templates/parent/base.html (idempotent — skips if already there)
4.  VIEWS     — appends missing view stubs to apps/parent_portal/views.py
5.  URLS      — patches apps/parent_portal/urls.py with missing patterns
6.  PESAPAL   — checks settings, adds payment initiation + IPN views
7.  LOGIN     — patches the accounts login redirect so parents land on /parent/

Run from project root:
    python expand_parent_portal_phase3.py
"""

import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def append_if_missing(path, needle, block):
    content = read(path)
    if needle in content:
        print(f"  [SKIP] Already present: {needle!r}")
        return False
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + block)
    print(f"  [ADD]  Appended to {os.path.relpath(path)}")
    return True

def find_settings():
    for rel in ["core/settings.py", "config/settings.py", "settings.py", "asms/settings.py"]:
        p = os.path.join(BASE_DIR, rel)
        if os.path.exists(p):
            return p
    return None

def find_urls():
    for rel in ["core/urls.py", "config/urls.py", "urls.py", "asms/urls.py"]:
        p = os.path.join(BASE_DIR, rel)
        if os.path.exists(p):
            return p
    return None

# ─────────────────────────────────────────────────────────────────────────────
# 1. DIAGNOSE
# ─────────────────────────────────────────────────────────────────────────────

def diagnose():
    print("\n" + "="*60)
    print("STEP 1 — DIAGNOSTIC")
    print("="*60)

    # Templates
    tpl_dir = os.path.join(BASE_DIR, "templates", "parent")
    if os.path.exists(tpl_dir):
        tpls = []
        for root, dirs, files in os.walk(tpl_dir):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), tpl_dir)
                tpls.append(rel)
        print(f"\nTemplates in templates/parent/  ({len(tpls)} found):")
        for t in sorted(tpls):
            print(f"    {t}")
    else:
        print(f"\n[WARN] templates/parent/ not found at {tpl_dir}")

    # Views
    views_path = os.path.join(BASE_DIR, "apps", "parent_portal", "views.py")
    if os.path.exists(views_path):
        content = read(views_path)
        defs = re.findall(r"^def (\w+)\(", content, re.MULTILINE)
        print(f"\nViews in apps/parent_portal/views.py  ({len(defs)} found):")
        for d in defs:
            print(f"    {d}")
    else:
        print("\n[WARN] apps/parent_portal/views.py not found")

    # URLs
    pp_urls = os.path.join(BASE_DIR, "apps", "parent_portal", "urls.py")
    if os.path.exists(pp_urls):
        content = read(pp_urls)
        names = re.findall(r"name=['\"](\w+)['\"]", content)
        print(f"\nURL names in apps/parent_portal/urls.py  ({len(names)} found):")
        for n in names:
            print(f"    parent:{n}")
    else:
        print("\n[WARN] apps/parent_portal/urls.py not found")

    # PesaPal settings
    settings_path = find_settings()
    if settings_path:
        cfg = read(settings_path)
        keys = ["PESAPAL_CONSUMER_KEY", "PESAPAL_CONSUMER_SECRET", "PESAPAL_IPN_URL"]
        print("\nPesaPal settings in settings.py:")
        for k in keys:
            found = k in cfg
            val = "✓" if found else "✗ MISSING"
            print(f"    {k}: {val}")

    print()

# ─────────────────────────────────────────────────────────────────────────────
# 2. STUDENT LINK GUIDE
# ─────────────────────────────────────────────────────────────────────────────

def student_link_guide():
    print("="*60)
    print("STEP 2 — LINK A TEST STUDENT")
    print("="*60)
    print("""
Run this in your Django shell to link an existing student to
the parent user you're testing with (adjust username/pk):

    python manage.py shell

    from django.contrib.auth import get_user_model
    from apps.students.models import Guardian

    User = get_user_model()
    parent = User.objects.get(username='YOUR_PARENT_USERNAME')

    # Option A — link via an existing Guardian record
    g = Guardian.objects.first()   # or Guardian.objects.get(pk=13)
    g.user = parent
    g.save()
    print(f"Linked {parent} → {g.student}")

    # Option B — create a fresh parent account
    parent = User.objects.create_user(
        username='parent_nakato',
        password='Test1234!',
        first_name='Sarah',
        last_name='Nakato',
        role='parent',
    )
    g = Guardian.objects.get(pk=13)   # real guardian pk
    g.user = parent
    g.save()
    print("Done.")

After linking, visit http://127.0.0.1:8000/parent/ — the
full sidebar (Academic, Attendance, Fees …) will appear.
""")

# ─────────────────────────────────────────────────────────────────────────────
# 3. SIDEBAR — add missing sections to base.html
# ─────────────────────────────────────────────────────────────────────────────

SIDEBAR_ADDITIONS = {
    # marker_in_existing_html: new_nav_html_block
    "parent:child_library": None,    # will check presence only
    "parent:child_timetable": None,
    "parent:child_canteen": None,
    "parent:child_health": None,
    "parent:child_transport": None,
}

SIDEBAR_LIBRARY_BLOCK = """\
  {# ── Library ── #}
  {% if nav_s %}
  <div class="pp-nav-grp">Library</div>
  <a href="{% url 'parent:child_library' nav_s.pk %}"
     class="pp-nav-link{% if active_section == 'library' %} active{% endif %}">
    <i class="bi bi-book-half"></i> Library
  </a>
  {% endif %}"""

SIDEBAR_TIMETABLE_BLOCK = """\
  {# ── Timetable ── #}
  {% if nav_s %}
  <div class="pp-nav-grp">Schedule</div>
  <a href="{% url 'parent:child_timetable' nav_s.pk %}"
     class="pp-nav-link{% if active_section == 'timetable' %} active{% endif %}">
    <i class="bi bi-calendar-week"></i> Timetable
  </a>
  {% endif %}"""

SIDEBAR_CANTEEN_BLOCK = """\
  {# ── Canteen (Phase 4) ── #}
  {% if nav_s %}
  <div class="pp-nav-grp">Services</div>
  <a href="{% url 'parent:child_canteen' nav_s.pk %}"
     class="pp-nav-link{% if active_section == 'canteen' %} active{% endif %}">
    <i class="bi bi-cup-straw"></i> Canteen
  </a>
  <a href="{% url 'parent:child_health' nav_s.pk %}"
     class="pp-nav-link{% if active_section == 'health' %} active{% endif %}">
    <i class="bi bi-heart-pulse"></i> Health
  </a>
  <a href="{% url 'parent:child_transport' nav_s.pk %}"
     class="pp-nav-link{% if active_section == 'transport' %} active{% endif %}">
    <i class="bi bi-bus-front"></i> Transport
  </a>
  {% endif %}"""

# anchor: insert new block just before </nav>
def patch_sidebar(base_html_path):
    print("="*60)
    print("STEP 3 — SIDEBAR EXPANSION")
    print("="*60)

    if not os.path.exists(base_html_path):
        print(f"  [WARN] Not found: {base_html_path}")
        return

    content = read(base_html_path)
    changed = False

    blocks = [
        ("parent:child_library",  SIDEBAR_LIBRARY_BLOCK),
        ("parent:child_timetable", SIDEBAR_TIMETABLE_BLOCK),
        ("parent:child_canteen",  SIDEBAR_CANTEEN_BLOCK),
    ]

    for marker, block in blocks:
        if marker in content:
            print(f"  [SKIP] {marker} already in sidebar")
        else:
            # Insert before </nav>
            if "</nav>" in content:
                content = content.replace("</nav>", block + "\n</nav>", 1)
                print(f"  [ADD]  {marker}")
                changed = True
            else:
                print(f"  [WARN] Could not find </nav> anchor — add {marker} manually")

    if changed:
        write(base_html_path, content)
        print(f"  [OK]   Saved {os.path.relpath(base_html_path)}")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# 4. VIEWS — append missing stubs
# ─────────────────────────────────────────────────────────────────────────────

MISSING_VIEW_STUBS = {
    "child_library": """\

# ── Library ─────────────────────────────────────────────────────────────────
@login_required
def child_library(request, student_pk):
    student = get_object_or_404(Student, pk=student_pk)
    _require_parent_access(request, student)

    borrow_records = []
    overdue_count = 0
    fine_total = 0
    try:
        from apps.library.models import BorrowRecord
        from django.utils import timezone
        now = timezone.now().date()
        qs = BorrowRecord.objects.filter(
            student=student
        ).select_related("book").order_by("-borrowed_date")
        borrow_records = list(qs)
        overdue_count = sum(1 for r in borrow_records
                            if r.due_date and r.due_date < now and not r.return_date)
        fine_total = sum(getattr(r, "fine_amount", 0) or 0 for r in borrow_records)
    except Exception:
        pass

    return render(request, "parent/child/library.html", {
        "active_section": "library",
        "student": student,
        "borrow_records": borrow_records,
        "overdue_count": overdue_count,
        "fine_total": fine_total,
    })
""",
    "child_timetable": """\

# ── Timetable ────────────────────────────────────────────────────────────────
@login_required
def child_timetable(request, student_pk):
    student = get_object_or_404(Student, pk=student_pk)
    _require_parent_access(request, student)

    timetable_slots = []
    try:
        from apps.academics.models import TimetableSlot
        timetable_slots = list(
            TimetableSlot.objects.filter(
                student_class=student.current_class
            ).select_related("subject", "teacher").order_by("day", "start_time")
        )
    except Exception:
        pass

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    grid = {day: [s for s in timetable_slots if s.day == day] for day in days}

    return render(request, "parent/child/timetable.html", {
        "active_section": "timetable",
        "student": student,
        "days": days,
        "grid": grid,
    })
""",
    "child_canteen": """\

# ── Canteen (Phase 4 placeholder) ────────────────────────────────────────────
@login_required
def child_canteen(request, student_pk):
    student = get_object_or_404(Student, pk=student_pk)
    _require_parent_access(request, student)
    return render(request, "parent/child/canteen.html", {
        "active_section": "canteen",
        "student": student,
        "phase": 4,
    })
""",
    "child_health": """\

# ── Health (Phase 4 placeholder) ─────────────────────────────────────────────
@login_required
def child_health(request, student_pk):
    student = get_object_or_404(Student, pk=student_pk)
    _require_parent_access(request, student)
    return render(request, "parent/child/health.html", {
        "active_section": "health",
        "student": student,
        "phase": 4,
    })
""",
    "child_transport": """\

# ── Transport (Phase 4 placeholder) ──────────────────────────────────────────
@login_required
def child_transport(request, student_pk):
    student = get_object_or_404(Student, pk=student_pk)
    _require_parent_access(request, student)
    return render(request, "parent/child/transport.html", {
        "active_section": "transport",
        "student": student,
        "phase": 4,
    })
""",
}

def ensure_require_parent_access(views_path):
    """Make sure _require_parent_access helper exists."""
    content = read(views_path)
    if "_require_parent_access" in content:
        return
    stub = """\

# ── Access guard ─────────────────────────────────────────────────────────────
def _require_parent_access(request, student):
    \"\"\"Raise 403 if the logged-in user is not a guardian of this student.\"\"\"
    from apps.students.models import Guardian
    from django.core.exceptions import PermissionDenied
    if request.user.is_superuser or getattr(request.user, "role", "") in (
        "super_admin", "school_admin", "principal"
    ):
        return
    ok = Guardian.objects.filter(user=request.user, student=student).exists()
    if not ok:
        raise PermissionDenied
"""
    with open(views_path, "a", encoding="utf-8") as f:
        f.write(stub)
    print("  [ADD]  _require_parent_access helper")

def patch_views():
    print("="*60)
    print("STEP 4 — VIEWS")
    print("="*60)

    views_path = os.path.join(BASE_DIR, "apps", "parent_portal", "views.py")
    if not os.path.exists(views_path):
        print(f"  [WARN] {views_path} not found — skipping")
        return

    ensure_require_parent_access(views_path)
    content = read(views_path)

    # Ensure Student import is present
    if "from apps.students.models import Student" not in content:
        content = content.replace(
            "from django.shortcuts import",
            "from apps.students.models import Student\nfrom django.shortcuts import",
        )
        write(views_path, content)
        print("  [ADD]  Student import")
        content = read(views_path)

    for fn_name, stub in MISSING_VIEW_STUBS.items():
        if f"def {fn_name}(" in content:
            print(f"  [SKIP] def {fn_name} already exists")
        else:
            with open(views_path, "a", encoding="utf-8") as f:
                f.write(stub)
            print(f"  [ADD]  def {fn_name}")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# 5. URLS — patch missing patterns
# ─────────────────────────────────────────────────────────────────────────────

MISSING_URL_PATTERNS = [
    ("child_library",
     "    path('child/<int:student_pk>/library/',   views.child_library,   name='child_library'),"),
    ("child_timetable",
     "    path('child/<int:student_pk>/timetable/', views.child_timetable, name='child_timetable'),"),
    ("child_canteen",
     "    path('child/<int:student_pk>/canteen/',   views.child_canteen,   name='child_canteen'),"),
    ("child_health",
     "    path('child/<int:student_pk>/health/',    views.child_health,    name='child_health'),"),
    ("child_transport",
     "    path('child/<int:student_pk>/transport/', views.child_transport, name='child_transport'),"),
]

def patch_urls():
    print("="*60)
    print("STEP 5 — URLS")
    print("="*60)

    urls_path = os.path.join(BASE_DIR, "apps", "parent_portal", "urls.py")
    if not os.path.exists(urls_path):
        print(f"  [WARN] {urls_path} not found — skipping")
        return

    content = read(urls_path)
    changed = False

    for name, pattern in MISSING_URL_PATTERNS:
        if f"name='{name}'" in content or f'name="{name}"' in content:
            print(f"  [SKIP] {name}")
        else:
            # Insert before the closing ] of urlpatterns
            if "]" in content:
                content = content.rstrip().rstrip("]").rstrip() + f"\n{pattern}\n]\n"
                print(f"  [ADD]  {name}")
                changed = True

    if changed:
        write(urls_path, content)
        print(f"  [OK]   Saved {os.path.relpath(urls_path)}")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# 6. TEMPLATES — write missing placeholder templates
# ─────────────────────────────────────────────────────────────────────────────

def placeholder_template(section_title, icon, coming_phase=None):
    phase_msg = f"<p class='text-muted mt-2'>Full feature arrives in Phase {coming_phase}.</p>" if coming_phase else ""
    return f"""{{% extends "parent/base.html" %}}
{{% block title %}}{section_title}{{% endblock %}}
{{% block content %}}
<div class="pp-card text-center py-5">
  <i class="bi {icon} fs-1 text-secondary"></i>
  <h5 class="mt-3">{section_title}</h5>
  {phase_msg}
</div>
{{% endblock %}}
"""

MISSING_TEMPLATES = {
    "parent/child/library.html": """\
{% extends "parent/base.html" %}
{% block title %}Library — {{ student.first_name }}{% endblock %}
{% block content %}
<div class="pp-card mb-3">
  <h5 class="mb-0">
    <i class="bi bi-book-half me-2 text-primary"></i>
    Library — {{ student.first_name }} {{ student.last_name }}
  </h5>
</div>

{% if overdue_count %}
<div class="alert alert-danger">
  <i class="bi bi-exclamation-triangle me-2"></i>
  {{ overdue_count }} overdue book{{ overdue_count|pluralize }} · Fine: UGX {{ fine_total|floatformat:0 }}
</div>
{% endif %}

{% if borrow_records %}
<div class="pp-card">
  <table class="table table-hover mb-0">
    <thead class="table-light">
      <tr>
        <th>Book</th><th>Borrowed</th><th>Due</th><th>Status</th>
      </tr>
    </thead>
    <tbody>
    {% for r in borrow_records %}
      <tr>
        <td>{{ r.book.title }}</td>
        <td>{{ r.borrowed_date|date:"d M Y" }}</td>
        <td>{{ r.due_date|date:"d M Y"|default:"—" }}</td>
        <td>
          {% if r.return_date %}
            <span class="badge bg-success">Returned</span>
          {% elif r.due_date and r.due_date < today %}
            <span class="badge bg-danger">Overdue</span>
          {% else %}
            <span class="badge bg-primary">On Loan</span>
          {% endif %}
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% else %}
<div class="pp-card text-center py-5">
  <i class="bi bi-book fs-1 text-secondary"></i>
  <p class="mt-3 text-muted">No library activity yet.</p>
</div>
{% endif %}
{% endblock %}
""",
    "parent/child/timetable.html": """\
{% extends "parent/base.html" %}
{% block title %}Timetable — {{ student.first_name }}{% endblock %}
{% block content %}
<div class="pp-card mb-3">
  <h5 class="mb-0">
    <i class="bi bi-calendar-week me-2 text-primary"></i>
    Timetable — {{ student.first_name }} {{ student.last_name }}
  </h5>
</div>

{% if not grid.Monday and not grid.Tuesday %}
<div class="pp-card text-center py-5">
  <i class="bi bi-calendar-x fs-1 text-secondary"></i>
  <p class="mt-3 text-muted">No timetable configured for this class yet.</p>
</div>
{% else %}
<div class="table-responsive">
<table class="table table-bordered text-center">
  <thead class="table-dark">
    <tr>
      {% for day in days %}<th>{{ day }}</th>{% endfor %}
    </tr>
  </thead>
  <tbody>
    <tr>
    {% for day in days %}
      <td class="align-top p-1">
        {% for slot in grid|get_item:day %}
        <div class="badge bg-primary mb-1 d-block">
          {{ slot.start_time|time:"H:i" }} {{ slot.subject.name }}
        </div>
        {% empty %}
        <span class="text-muted small">—</span>
        {% endfor %}
      </td>
    {% endfor %}
    </tr>
  </tbody>
</table>
</div>
{% endif %}
{% endblock %}
""",
    "parent/child/canteen.html": placeholder_template(
        "Canteen", "bi-cup-straw", coming_phase=4),
    "parent/child/health.html": placeholder_template(
        "Health & Medical", "bi-heart-pulse", coming_phase=4),
    "parent/child/transport.html": placeholder_template(
        "Transport & Routes", "bi-bus-front", coming_phase=4),
}

def patch_templates():
    print("="*60)
    print("STEP 6 — TEMPLATES")
    print("="*60)

    tpl_base = os.path.join(BASE_DIR, "templates")

    for rel_path, content in MISSING_TEMPLATES.items():
        full_path = os.path.join(tpl_base, rel_path)
        if os.path.exists(full_path):
            print(f"  [SKIP] {rel_path}")
        else:
            write(full_path, content)
            print(f"  [ADD]  {rel_path}")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# 7. PESAPAL — check config + add initiation view stub
# ─────────────────────────────────────────────────────────────────────────────

PESAPAL_SETTINGS_BLOCK = """\

# ── PesaPal Payment Gateway ───────────────────────────────────────────────────
# Sign up at https://www.pesapal.com/  →  Dashboard → Applications → API credentials
PESAPAL_CONSUMER_KEY    = os.environ.get("PESAPAL_CONSUMER_KEY", "")
PESAPAL_CONSUMER_SECRET = os.environ.get("PESAPAL_CONSUMER_SECRET", "")
PESAPAL_IPN_URL         = os.environ.get("PESAPAL_IPN_URL", "https://yourdomain.com/payments/ipn/")
PESAPAL_SANDBOX         = True   # Set False in production
"""

PESAPAL_VIEW_STUB = '''\

# ── PesaPal integration (apps/parent_portal/views.py) ────────────────────────
# The fees.html template calls {% url 'payments:initiate' invoice_pk=inv.pk %}
# That resolves to apps/payments/views.py  →  initiate_payment()
# The stub below is here for reference ONLY — actual implementation lives
# in apps/payments/views.py and apps/payments/pesapal.py
#
# To test:
#   1. Add PESAPAL_CONSUMER_KEY + PESAPAL_CONSUMER_SECRET to .env / settings.py
#   2. Set PESAPAL_SANDBOX=True for testing
#   3. Hit /parent/child/<pk>/fees/ and click "Pay Now"
#
# See: https://developer.pesapal.com/how-to-integrate/api-30-and-above
'''

def patch_pesapal():
    print("="*60)
    print("STEP 7 — PESAPAL CONFIGURATION")
    print("="*60)

    settings_path = find_settings()
    if not settings_path:
        print("  [WARN] settings.py not found")
        return

    content = read(settings_path)

    if "PESAPAL_CONSUMER_KEY" in content:
        print("  [SKIP] PesaPal settings already in settings.py")
    else:
        with open(settings_path, "a", encoding="utf-8") as f:
            f.write(PESAPAL_SETTINGS_BLOCK)
        print(f"  [ADD]  PesaPal settings block appended to {os.path.relpath(settings_path)}")
        print()
        print("  *** ACTION REQUIRED ***")
        print("  Set these environment variables (or update settings.py directly):")
        print("    PESAPAL_CONSUMER_KEY    = <from PesaPal dashboard>")
        print("    PESAPAL_CONSUMER_SECRET = <from PesaPal dashboard>")
        print("    PESAPAL_IPN_URL         = https://yourdomain.com/payments/ipn/")
        print()
        print("  For local dev, put them in a .env file and use python-dotenv:")
        print("    pip install python-dotenv")
        print("    # In settings.py top:")
        print("    from dotenv import load_dotenv; load_dotenv()")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# 8. LOGIN REDIRECT — route parents to /parent/
# ─────────────────────────────────────────────────────────────────────────────

def patch_login_redirect():
    print("="*60)
    print("STEP 8 — LOGIN REDIRECT (parent → /parent/)")
    print("="*60)

    # Find accounts views.py
    accounts_views = os.path.join(BASE_DIR, "apps", "accounts", "views.py")
    if not os.path.exists(accounts_views):
        print("  [WARN] apps/accounts/views.py not found")
        print("  Manually add this to your login redirect logic:")
        print("      if user.role == 'parent': return '/parent/'")
        return

    content = read(accounts_views)

    # Check if already redirecting parents
    if "/parent/" in content and "role" in content:
        print("  [SKIP] Parent redirect already in accounts/views.py")
        return

    # Try to find the dashboard redirect function and inject parent routing
    # Common patterns: get_dashboard_url, login_redirect, get_success_url
    pattern = re.compile(
        r"(def get_dashboard_url\(.*?\).*?)(return\s+['\"]/?dashboard['\"])",
        re.DOTALL
    )
    if pattern.search(content):
        content = pattern.sub(
            r"\1if getattr(user, 'role', '') == 'parent':\n        return '/parent/'\n    \2",
            content
        )
        write(accounts_views, content)
        print("  [ADD]  Parent → /parent/ in get_dashboard_url()")
    else:
        print("  [INFO] Could not auto-patch — add manually to login redirect:")
        print("         if user.role == 'parent': return '/parent/'")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("ASMS — Parent Portal Phase 3 Expansion")
    print("="*60)

    base_html = os.path.join(BASE_DIR, "templates", "parent", "base.html")

    diagnose()
    student_link_guide()
    patch_sidebar(base_html)
    patch_views()
    patch_urls()
    patch_templates()
    patch_pesapal()
    patch_login_redirect()

    print("="*60)
    print("DONE. Next steps:")
    print()
    print("  1. python manage.py check")
    print("  2. python manage.py makemigrations")
    print("  3. python manage.py migrate")
    print("  4. Link a test student (see Step 2 output above)")
    print("  5. python manage.py runserver")
    print("  6. Visit http://127.0.0.1:8000/parent/  (Ctrl+Shift+R)")
    print()
    print("The sidebar will show all new sections once a student is linked.")
    print("PesaPal pay button activates once credentials are in settings.")
    print("="*60)

if __name__ == "__main__":
    main()
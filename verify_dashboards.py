"""
Verifies role dashboards were built correctly and fixes any issues.
Run from project root: python verify_dashboards.py
"""
import os, re

ROOT = os.getcwd()
APPS = os.path.join(ROOT, 'apps')
TMPL = os.path.join(ROOT, 'templates', 'dashboard')

print("\n═══ Verifying Role Dashboards ═══\n")

# ── 1. Check templates exist ──────────────────────────────────────────────
expected = ['teacher.html', 'finance.html', 'welfare.html',
            'library.html', 'principal.html']
for tmpl in expected:
    path = os.path.join(TMPL, tmpl)
    exists = os.path.exists(path)
    print(f"  {'✓' if exists else '✗'} templates/dashboard/{tmpl}")

# ── 2. Find which views file has the dashboards ───────────────────────────
views_file = None
for candidate in [
    os.path.join(APPS, 'dashboard', 'views.py'),
    os.path.join(APPS, 'core', 'views.py'),
]:
    if os.path.exists(candidate):
        with open(candidate, encoding='utf-8') as f:
            content = f.read()
        if 'teacher_dashboard' in content:
            views_file = candidate
            print(f"\n  ✓ Role views found in: {candidate}")
            break

if not views_file:
    print("\n  ✗ Role dashboard views NOT found — script may not have run yet")

# ── 3. Find which urls file has the dashboard URLs ────────────────────────
urls_file = None
for candidate in [
    os.path.join(APPS, 'dashboard', 'urls.py'),
    os.path.join(APPS, 'core', 'urls.py'),
]:
    if os.path.exists(candidate):
        with open(candidate, encoding='utf-8') as f:
            uc = f.read()
        if 'teacher_dashboard' in uc:
            urls_file = candidate
            print(f"  ✓ Role URLs found in: {candidate}")
            # Show the namespace if any
            ns_match = re.search(r"app_name\s*=\s*['\"](\w+)['\"]", uc)
            if ns_match:
                namespace = ns_match.group(1)
                print(f"  ℹ Dashboard namespace: '{namespace}'")
                print(f"    Templates must use: {{% url '{namespace}:teacher_dashboard' %}}")
            else:
                print(f"  ℹ No namespace — templates use: {{% url 'teacher_dashboard' %}}")
            break

# ── 4. Find the Phase 1 URL namespaces ───────────────────────────────────
print("\n  Phase 1 app namespaces:")
namespaces = {}
for app_dir in os.listdir(APPS):
    urls_path = os.path.join(APPS, app_dir, 'urls.py')
    if os.path.exists(urls_path):
        with open(urls_path, encoding='utf-8') as f:
            uc = f.read()
        ns = re.search(r"app_name\s*=\s*['\"](\w+)['\"]", uc)
        if ns:
            namespaces[app_dir] = ns.group(1)
            print(f"    {app_dir:20s} → namespace: '{ns.group(1)}'")

# ── 5. Fix template URLs to use correct namespaces ───────────────────────
print("\n  Fixing template URL references...")

# Map of view names → their correct namespace prefix
# Based on what namespaces we found
url_fixes = {}
for app, ns in namespaces.items():
    if app == 'students':
        url_fixes.update({
            "'student_detail'":  f"'{ns}:student_detail'",
            "'student_list'":    f"'{ns}:student_list'",
            "'student_create'":  f"'{ns}:student_create'",
        })
    elif app == 'finance':
        url_fixes.update({
            "'invoice_detail'":  f"'{ns}:invoice_detail'",
            "'invoice_create'":  f"'{ns}:invoice_create'",
            "'invoice_list'":    f"'{ns}:invoice_list'",
            "'finance_summary'": f"'{ns}:finance_summary'",
        })
    elif app == 'attendance':
        url_fixes.update({
            "'attendance_mark'":   f"'{ns}:mark'",
            "'attendance_report'": f"'{ns}:report'",
        })
    elif app == 'admissions':
        url_fixes.update({
            "'application_list'":   f"'{ns}:application_list'",
            "'application_create'": f"'{ns}:application_create'",
        })
    elif app == 'staff_hr':
        url_fixes.update({
            "'leave_list'":   f"'{ns}:leave_list'",
            "'leave_apply'":  f"'{ns}:leave_apply'",
            "'staff_list'":   f"'{ns}:staff_list'",
            "'staff_create'": f"'{ns}:staff_create'",
            "'cpd_list'":     f"'{ns}:cpd_list'",
        })

fixes_applied = 0
for tmpl_name in expected:
    tmpl_path = os.path.join(TMPL, tmpl_name)
    if not os.path.exists(tmpl_path):
        continue
    with open(tmpl_path, encoding='utf-8') as f:
        content = f.read()
    original = content
    for old_url, new_url in url_fixes.items():
        content = content.replace(old_url, new_url)
    if content != original:
        with open(tmpl_path, 'w', encoding='utf-8') as f:
            f.write(content)
        fixes_applied += 1
        print(f"    ✓ Fixed namespace refs in dashboard/{tmpl_name}")

if fixes_applied == 0:
    print("    ✓ No namespace fixes needed")

# ── 6. Print get_dashboard_url current state ────────────────────────────
print("\n  Current get_dashboard_url() URLs:")
acct = os.path.join(APPS, 'accounts', 'models.py')
with open(acct, encoding='utf-8') as f:
    acct_content = f.read()
m = re.search(r'def get_dashboard_url.*?return role_urls', acct_content, re.DOTALL)
if m:
    lines = m.group(0).split('\n')
    for line in lines:
        if "'/dashboard" in line or "'/portal" in line:
            print(f"    {line.strip()}")

print(f"""
═══════════════════════════════════════════════════════════
  Verification complete.

  Test each role by logging in as:
  Role          Login URL
  ─────────────────────────────────────────────────────
  Admin       → /accounts/login/  (admin account)
  Teacher     → /accounts/login/  (teacher account)
  Accountant  → /accounts/login/  (accountant account)
  Counsellor  → /accounts/login/  (counsellor account)
  Librarian   → /accounts/login/  (librarian account)
  Principal   → /accounts/login/  (principal account)

  Each role lands on their own dashboard automatically.
═══════════════════════════════════════════════════════════
""")

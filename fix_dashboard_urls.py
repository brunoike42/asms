#!/usr/bin/env python
"""
fix_dashboard_urls.py
Reads your actual URL files, finds exact names + namespaces,
then fixes the dashboard template Quick Actions URLs accordingly.
Run from project root: python fix_dashboard_urls.py
"""
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def r(p): return os.path.join(BASE, p)
def read(p):
    with open(r(p), encoding='utf-8') as f: return f.read()
def write(p, c):
    with open(r(p), 'w', encoding='utf-8') as f: f.write(c)

print("="*60)
print("Fixing dashboard template URL names")
print("="*60)

# ── Read each url file and extract app_name + names ─────────────────────────
info = {}
for app in ['students','finance','attendance','admissions','core','accounts']:
    path = f'apps/{app}/urls.py'
    if not os.path.exists(r(path)):
        continue
    content = read(path)
    app_name_m = re.search(r"app_name\s*=\s*['\"]([^'\"]+)['\"]", content)
    app_name = app_name_m.group(1) if app_name_m else None
    # Extract path(..., name='...') entries — get both the path and name
    patterns = re.findall(
        r"path\(['\"]([^'\"]*)['\"].*?name=['\"]([^'\"]+)['\"]",
        content
    )
    info[app] = {
        'app_name': app_name,
        'urls': patterns,
    }

print("\n── Discovered URL names ─────────────────────────────────────────")
for app, data in info.items():
    prefix = f"{data['app_name']}:" if data['app_name'] else "(no namespace)"
    print(f"\n{app}/urls.py  [app_name={data['app_name']}]")
    for path_str, name in data['urls']:
        full = f"{data['app_name']}:{name}" if data['app_name'] else name
        print(f"  path='{path_str}'  →  {{% url '{full}' %}}")

# ── Work out the correct URLs for Quick Actions ──────────────────────────────
print("\n── Resolving Quick Action URLs ──────────────────────────────────")

def find_url(app, keywords):
    """Find best URL name match for given keywords."""
    data = info.get(app, {})
    app_name = data.get('app_name')
    urls = data.get('urls', [])
    for kw in keywords:
        for path_str, name in urls:
            if kw in name.lower() or kw in path_str.lower():
                return f"{app_name}:{name}" if app_name else name
    # fallback: return first url in app
    if urls:
        name = urls[0][1]
        return f"{app_name}:{name}" if app_name else name
    return None

student_list_url  = find_url('students', ['list','index','student_list',''])
student_add_url   = find_url('students', ['add','new','create','enrol','enroll'])
classroom_url     = find_url('students', ['classroom','class','room'])
attendance_url    = find_url('attendance', ['home','index','list',''])
invoice_url       = find_url('finance', ['invoice_list','invoice','list'])

print(f"  Students list:    {{{{ url '{student_list_url}' }}}}")
print(f"  Add student:      {{{{ url '{student_add_url}' }}}}")
print(f"  Classrooms:       {{{{ url '{classroom_url}' }}}}")
print(f"  Attendance home:  {{{{ url '{attendance_url}' }}}}")
print(f"  Invoice list:     {{{{ url '{invoice_url}' }}}}")

# ── Fix the dashboard template ────────────────────────────────────────────────
tmpl_candidates = ['templates/dashboard/dashboard.html', 'templates/core/dashboard.html']
tmpl_path = None
for tc in tmpl_candidates:
    if os.path.exists(r(tc)):
        tmpl_path = tc
        break

if not tmpl_path:
    print("\nERROR: Dashboard template not found. Run upgrade_dashboard.py first.")
    raise SystemExit(1)

content = read(tmpl_path)
original = content

replacements = {
    "{% url 'students:list' %}":      f"{{% url '{student_list_url}' %}}",
    "{% url 'students:add' %}":       f"{{% url '{student_add_url}' %}}",
    "{% url 'students:classrooms' %}":f"{{% url '{classroom_url}' %}}",
    "{% url 'attendance:home' %}":     f"{{% url '{attendance_url}' %}}",
    "{% url 'invoice_list' %}":        f"{{% url '{invoice_url}' %}}",
}

for old, new in replacements.items():
    if old in content:
        content = content.replace(old, new)
        print(f"\n  Fixed: {old}")
        print(f"      → {new}")
    else:
        print(f"\n  (already correct or missing): {old}")

if content != original:
    write(tmpl_path, content)
    print(f"\n✓ Template updated: {tmpl_path}")
else:
    print("\n  No changes needed — all URLs already correct.")

print("""
─────────────────────────────────────────────────────────────
Now open:  http://127.0.0.1:8000/dashboard/

If you still see NoReverseMatch errors, paste the error here
and I will fix the remaining URLs in one go.
─────────────────────────────────────────────────────────────
""")
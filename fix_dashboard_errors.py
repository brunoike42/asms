#!/usr/bin/env python
"""
fix_dashboard_error.py
Fixes the VariableDoesNotExist at /dashboard/ caused by
the |default:user.username filter on line 11.

Also adds django.contrib.humanize to INSTALLED_APPS if missing.
Run from project root: python fix_dashboard_error.py
"""
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))
def r(p): return os.path.join(BASE, p)
def read(p): return open(r(p), encoding='utf-8').read()
def write(p, c): open(r(p), 'w', encoding='utf-8').write(c)

print("=" * 60)
print("Fix: VariableDoesNotExist at /dashboard/")
print("=" * 60)

# ── Fix 1: Dashboard template — line 11 ─────────────────────────────────────
# The pattern |default:user.username causes Django's template engine to resolve
# user.username as a filter argument on the SimpleLazyObject, which raises
# VariableDoesNotExist before the attribute lookup can succeed.
# Replace with an explicit {% if %} block which is always safe.

tmpl_candidates = [
    'templates/dashboard/dashboard.html',
    'templates/core/dashboard.html',
]
tmpl_path = None
for tc in tmpl_candidates:
    if os.path.exists(r(tc)):
        tmpl_path = tc
        break

if not tmpl_path:
    print("ERROR: Dashboard template not found.")
    raise SystemExit(1)

content = read(tmpl_path)

OLD_LINE = "{{ user.get_full_name|default:user.username }}"
NEW_LINE  = "{% if user.get_full_name %}{{ user.get_full_name }}{% else %}{{ user.username }}{% endif %}"

if OLD_LINE in content:
    content = content.replace(OLD_LINE, NEW_LINE)
    write(tmpl_path, content)
    print(f"\n[1] Fixed in {tmpl_path}:")
    print(f"    Before: {{{{ user.get_full_name|default:user.username }}}}")
    print(f"    After:  {{% if user.get_full_name %}}{{{{ user.get_full_name }}}}{{% else %}}{{{{ user.username }}}}{{% endif %}}")
else:
    print(f"\n[1] Pattern not found in template — may already be fixed.")
    # Try to find any remaining |default:user. patterns that could cause same issue
    bad = re.findall(r'\|default:user\.\w+', content)
    if bad:
        print(f"    Found other risky default patterns: {bad}")
        for b in bad:
            var = b.replace('|default:', '')
            safe = f"{{% if {var} %}}{{{{{var}}}}}{{% else %}}{{{{{var}}}}}{{% endif %}}"
            content = content.replace(b, '')  # just remove the risky default
        write(tmpl_path, content)
        print("    Removed risky |default:variable patterns.")

# ── Fix 2: Ensure django.contrib.humanize is in INSTALLED_APPS ──────────────
# The template uses {% load humanize %} + |intcomma — needs humanize installed.
settings_path = None
for sp in ['config/settings.py', 'asms/settings.py', 'core/settings.py']:
    if os.path.exists(r(sp)):
        settings_path = sp
        break

if settings_path:
    s = read(settings_path)
    if 'django.contrib.humanize' not in s:
        # Add it after django.contrib.staticfiles or django.contrib.messages
        for anchor in ["'django.contrib.staticfiles'", "'django.contrib.messages'"]:
            if anchor in s:
                s = s.replace(anchor, anchor + "\n    'django.contrib.humanize',")
                write(settings_path, s)
                print(f"\n[2] Added 'django.contrib.humanize' to INSTALLED_APPS in {settings_path}")
                break
        else:
            print(f"\n[2] WARNING: Could not auto-add humanize. Add it manually to INSTALLED_APPS in {settings_path}")
    else:
        print(f"\n[2] django.contrib.humanize already in INSTALLED_APPS ✓")
else:
    print("\n[2] Could not find settings.py to check humanize.")

# ── Fix 3: Make |intcomma safe — wrap with filter check ─────────────────────
# If for any reason humanize isn't loaded, |intcomma fails. 
# Ensure the template has {% load humanize %} at the top (after extends).
content = read(tmpl_path)
if '{% load humanize %}' not in content:
    content = content.replace(
        '{% extends "base/base.html" %}',
        '{% extends "base/base.html" %}\n{% load humanize %}'
    )
    write(tmpl_path, content)
    print("\n[3] Added {% load humanize %} to template top.")
else:
    print("\n[3] {% load humanize %} already present ✓")

print("""
──────────────────────────────────────────────────────────────
✅  Done. Restart your server and open /dashboard/

  python manage.py runserver

If any new error appears, paste it here.
──────────────────────────────────────────────────────────────
""")
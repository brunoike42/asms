# fix_portal_templates.py
import os
import re

BASE = 'apps/parent_portal/templates'
fixes = 0

for root, dirs, files in os.walk(BASE):
    for fname in files:
        if not fname.endswith('.html'):
            continue
        fpath = os.path.join(root, fname)
        content = open(fpath, encoding='utf-8').read()
        original = content

        # Fix 1: All bare url 'dashboard' → namespaced
        content = content.replace("url 'dashboard'", "url 'parent:dashboard'")
        content = content.replace('url "dashboard"', 'url "parent:dashboard"')

        # Fix 2: Remove invalid {% break %} — Django templates don't support it
        content = re.sub(r'\{%[-\s]*break\s*[-\s]*%\}', '', content)

        # Fix 3: Any other bare parent URL names missing namespace
        for name in ['profile', 'notifications', 'child_detail', 'child_fees',
                     'child_attendance', 'child_academic', 'child_behaviour',
                     'messages', 'absence_excuse']:
            content = content.replace(f"url '{name}'", f"url 'parent:{name}'")
            content = content.replace(f'url "{name}"', f'url "parent:{name}"')

        if content != original:
            open(fpath, 'w', encoding='utf-8').write(content)
            fixes += 1
            print(f'  Fixed: {fpath}')

print(f'\nDone — {fixes} file(s) patched.')
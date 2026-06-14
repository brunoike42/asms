# fix_root_parent_templates.py
import os, re

BASE = 'templates/parent'
fixes = 0

for root, dirs, files in os.walk(BASE):
    for fname in files:
        if not fname.endswith('.html'):
            continue
        fpath = os.path.join(root, fname)
        content = open(fpath, encoding='utf-8').read()
        original = content

        # Fix 1: Remove {% break %} — not valid in Django templates
        content = re.sub(r'\{%-?\s*break\s*-?%\}', '', content)

        # Fix 2: Bare 'dashboard' url tag → namespaced
        content = content.replace("url 'dashboard'", "url 'parent:dashboard'")
        content = content.replace('url "dashboard"', 'url "parent:dashboard"')

        # Fix 3: Any other bare parent URL names missing namespace
        for name in ['profile', 'notifications', 'notification_count',
                     'child_academic', 'child_attendance', 'child_fees',
                     'child_behaviour', 'child_assignments', 'child_documents',
                     'child_meetings', 'book_meeting']:
            content = content.replace(f"url '{name}'", f"url 'parent:{name}'")
            content = content.replace(f'url "{name}"', f'url "parent:{name}"')

        if content != original:
            open(fpath, 'w', encoding='utf-8').write(content)
            fixes += 1
            print(f'  Fixed: {fpath}')

print(f'\nDone — {fixes} file(s) patched.')
print('\nNOTE: Going forward, edit templates in:')
print('  templates/parent/       ← ROOT (what Django actually loads)')
print('  NOT apps/parent_portal/templates/parent/  ← ignored by Django')
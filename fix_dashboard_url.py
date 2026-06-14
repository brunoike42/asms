# fix_dashboard_urls.py
# Run from E:\DJANGO\ASMS\asms\

path = 'apps/accounts/models.py'
content = open(path, encoding='utf-8').read()

# Fix parent portal URL
content = content.replace(
    "self.RoleChoices.PARENT:         '/dashboard/parent/',",
    "self.RoleChoices.PARENT:         '/parent/',"
)

# Fix student portal URL (future-proofing)
content = content.replace(
    "self.RoleChoices.STUDENT:        '/dashboard/student/',",
    "self.RoleChoices.STUDENT:        '/student/',"
)

open(path, 'w', encoding='utf-8').write(content)

# Verify the fix
import re
match = re.search(r'role_urls = \{(.+?)\}', content, re.DOTALL)
if match:
    print("Fixed get_dashboard_url():")
    print(match.group(0))
else:
    print("Could not verify - check manually")
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
u = User.objects.get(email="student@stamarys.ac.ug")
print(f"first_name: {u.first_name}")
print(f"last_name:  {u.last_name}")
print(f"username:   {u.username}")
print(f"role:       {getattr(u, 'role', 'N/A')}")
print(f"tenant_id:  {getattr(u, 'tenant_id', 'N/A')}")

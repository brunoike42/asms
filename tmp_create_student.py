import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.contrib.auth import get_user_model
from apps.students.models import Student
User = get_user_model()
u = User.objects.get(email="student@stamarys.ac.ug")
# Check no Student already claims this user
if Student.objects.filter(user=u).exists():
    print("Already linked:", Student.objects.get(user=u).pk)
else:
    s = Student.objects.create(
        user=u,
        tenant=u.tenant,
        first_name=u.first_name,
        last_name=u.last_name,
    )
    print(f"Created and linked: Student pk={s.pk}  {s.first_name} {s.last_name}")

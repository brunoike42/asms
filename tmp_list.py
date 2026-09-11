import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from apps.students.models import Student
for s in Student.objects.filter(user__isnull=True, tenant_id=1).order_by("pk"):
    print(s.pk, s.first_name, s.last_name)

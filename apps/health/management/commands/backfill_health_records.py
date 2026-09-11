from django.core.management.base import BaseCommand
from apps.students.models import Student
from apps.health.models import StudentHealthRecord
class Command(BaseCommand):
    help = "Creates a StudentHealthRecord for any existing student that does not already have one."
    def handle(self, *args, **options):
        created = 0
        for student in Student.objects.all():
            _, was_created = StudentHealthRecord.objects.get_or_create(
                tenant=student.tenant,
                student=student,
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Created {created} new health record(s)."))

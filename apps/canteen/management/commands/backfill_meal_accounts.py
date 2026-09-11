from django.core.management.base import BaseCommand
from apps.students.models import Student
from apps.canteen.models import MealAccount
class Command(BaseCommand):
    help = 'Creates a MealAccount for any existing Student that does not already have one.'
    def handle(self, *args, **options):
        created = 0
        for student in Student.objects.all():
            _, was_created = MealAccount.objects.get_or_create(
                tenant=student.tenant, student=student, defaults={'balance': 0}
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created} new meal account(s).'))

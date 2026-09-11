from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.students.models import Student

User = get_user_model()


class Command(BaseCommand):
    help = "Link Student rows to User accounts by matching on email or student_id."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Preview matches without saving.",
        )
        parser.add_argument(
            '--tenant',
            type=int,
            default=None,
            help="Restrict to a specific tenant_id.",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tenant_id = options['tenant']

        qs = Student.objects.filter(user__isnull=True)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        self.stdout.write(f"Unlinked students to process: {qs.count()}")

        linked = 0
        skipped = 0
        ambiguous = 0

        for student in qs.select_related('tenant'):
            user = None

            # Strategy 1: match by email field on Student (if your model has one)
            if hasattr(student, 'email') and student.email:
                try:
                    user = User.objects.get(email=student.email)
                except User.DoesNotExist:
                    pass
                except User.MultipleObjectsReturned:
                    self.stderr.write(
                        f"  AMBIGUOUS  Student #{student.pk} — "
                        f"multiple users for email {student.email}"
                    )
                    ambiguous += 1
                    continue

            # Strategy 2: match by student_id pattern in email
            # e.g. S2024001@stamarys.ac.ug → student_id = S2024001
            if user is None and hasattr(student, 'student_id') and student.student_id:
                email_guess = f"{student.student_id.lower()}@{student.tenant.domain}"
                try:
                    user = User.objects.get(email=email_guess)
                except User.DoesNotExist:
                    pass

            if user is None:
                self.stdout.write(
                    f"  SKIP  Student #{student.pk} "
                    f"{student.first_name} {student.last_name} — no matching user found"
                )
                skipped += 1
                continue

            # Guard: don't steal a user already linked to another student
            if Student.objects.filter(user=user).exclude(pk=student.pk).exists():
                self.stderr.write(
                    f"  CONFLICT  Student #{student.pk} — "
                    f"user {user.email} already linked to another student"
                )
                ambiguous += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  DRY-RUN  Student #{student.pk} "
                    f"{student.first_name} {student.last_name} "
                    f"→ {user.email}"
                )
            else:
                student.user = user
                student.save(update_fields=['user'])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  LINKED  Student #{student.pk} "
                        f"{student.first_name} {student.last_name} "
                        f"→ {user.email}"
                    )
                )
            linked += 1

        self.stdout.write(
            f"\nDone — linked: {linked}  skipped: {skipped}  "
            f"ambiguous/conflict: {ambiguous}"
        )
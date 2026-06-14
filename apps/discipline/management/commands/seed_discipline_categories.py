"""
Usage:
    python manage.py seed_discipline_categories --tenant-id 1

Seeds the 20 most common discipline categories with sensible defaults.
Safe to run multiple times (uses get_or_create).
"""
from django.core.management.base import BaseCommand, CommandError


DEFAULT_CATEGORIES = [
    # (name, code, default_severity, requires_approval, triggers_counselling)
    ('Fighting / Physical Assault',    'FIGHT',   'serious',  True,  False),
    ('Bullying',                        'BULLY',   'serious',  True,  True),
    ('Cyberbullying',                   'CYBRBUL', 'serious',  True,  True),
    ('Verbal Abuse / Threatening',      'VERBAL',  'moderate', False, False),
    ('Insubordination / Defiance',      'INSUB',   'moderate', False, False),
    ('Truancy / Unauthorised Absence',  'TRUAN',   'moderate', False, False),
    ('Late Coming',                     'LATE',    'minor',    False, False),
    ('Cheating / Academic Dishonesty',  'CHEAT',   'moderate', False, False),
    ('Property Damage / Vandalism',     'VANDAL',  'serious',  True,  False),
    ('Theft',                           'THEFT',   'serious',  True,  False),
    ('Substance Abuse',                 'SUBST',   'critical', True,  True),
    ('Possession of Prohibited Items',  'PROHIB',  'serious',  True,  False),
    ('Inappropriate Conduct',           'MISC',    'minor',    False, False),
    ('Disruption of Learning',          'DISRUPT', 'minor',    False, False),
    ('Disrespect to Staff',             'DISRSP',  'moderate', False, False),
    ('Harassment / Sexual Misconduct',  'HARASS',  'critical', True,  True),
    ('Social Media Misuse',             'SOCIAL',  'moderate', False, False),
    ('Uniform Violation',               'UNIFRM',  'minor',    False, False),
    ('Gambling',                        'GAMBLE',  'moderate', True,  False),
    ('Other Misconduct',                'OTHER',   'minor',    False, False),
]


class Command(BaseCommand):
    help = 'Seed default discipline categories for a tenant'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            required=True,
            help='The ID of the tenant (school) to seed categories for',
        )

    def handle(self, *args, **options):
        from apps.tenants.models import Tenant
        from apps.discipline.models import DisciplineCategory

        tenant_id = options['tenant_id']
        try:
            tenant = Tenant.objects.get(pk=tenant_id)
        except Tenant.DoesNotExist:
            raise CommandError(f'Tenant with ID {tenant_id} does not exist.')

        created_count = 0
        for name, code, severity, needs_approval, triggers_counselling in DEFAULT_CATEGORIES:
            _, created = DisciplineCategory.objects.get_or_create(
                tenant=tenant,
                name=name,
                defaults={
                    'code': code,
                    'default_severity': severity,
                    'requires_principal_approval': needs_approval,
                    'triggers_counselling': triggers_counselling,
                    'is_active': True,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'  Created: {name}')
            else:
                self.stdout.write(self.style.WARNING(f'  Already exists: {name}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. Created {created_count} new categories for "{tenant}".'
            )
        )

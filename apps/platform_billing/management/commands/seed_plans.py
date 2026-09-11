"""
Seeds the six Plan rows, now including the feature-list content shown on
the pricing page. Safe to re-run: uses update_or_create keyed on slug.

    python manage.py seed_plans
"""
from django.core.management.base import BaseCommand
from apps.platform_billing.models import Plan


PLANS = [
    dict(
        slug='trial', name='Free Trial',
        description='14-day free trial — full access, no card required',
        base_price=0, included_students=None, max_students=None, price_per_extra_student=0,
        max_users=None, storage_gb=5, sms_bundle=0,
        billing_interval=Plan.BillingIntervalChoices.CUSTOM,
        # Not a selectable billing plan on the pricing page -- every signup
        # gets 14 free days regardless of which paid tier they're trialing
        # into. This used to be True, which let 'trial' get picked as the
        # actual tenant.plan -- base_price=0 forever, so that tenant would
        # never actually be billed anything once the trial ended. Fixed here.
        is_self_serve=False,
        included_features=[], not_included=[],
    ),
    dict(
        slug='starter', name='Starter',
        description='Best for a small school going paperless for the first time',
        base_price=150000, included_students=300, max_students=300, price_per_extra_student=0,
        max_users=3, storage_gb=5, sms_bundle=0,
        billing_interval=Plan.BillingIntervalChoices.MONTHLY, is_self_serve=True,
        included_features=[
            'Up to 300 students', '3 staff accounts', '5GB file storage',
            'Student records & admissions', 'Daily attendance & timetables',
            'Fee invoicing & report cards', 'Bulk SMS to parents',
        ],
        not_included=[
            'No online MoMo/Card payments — fees recorded manually',
            'No LMS, discipline, or counselling tools',
        ],
    ),
    dict(
        slug='growth', name='Growth',
        description='Most schools choose this — everything digital, nothing missing',
        base_price=350000, included_students=400, max_students=800, price_per_extra_student=400,
        max_users=20, storage_gb=20, sms_bundle=500,
        billing_interval=Plan.BillingIntervalChoices.MONTHLY, is_self_serve=True,
        included_features=[
            'Up to 800 students', '20 staff accounts', '20GB storage + 500 SMS/month',
            'Everything in Starter, plus:', 'Full LMS with assignments & quizzes',
            'Online MTN, Airtel & Card payments', 'Discipline, counselling, canteen, transport',
        ],
        not_included=[
            'Biometric attendance and API access are Professional-only',
        ],
    ),
    dict(
        slug='professional', name='Professional',
        description='For large schools that need biometric check-in or integrations',
        base_price=700000, included_students=800, max_students=2000, price_per_extra_student=500,
        max_users=None, storage_gb=100, sms_bundle=1500,
        billing_interval=Plan.BillingIntervalChoices.MONTHLY, is_self_serve=True,
        included_features=[
            'Up to 2,000 students', 'Unlimited staff accounts', '100GB storage + 1,500 SMS/month',
            'Everything in Growth, plus:', 'Biometric attendance', 'API access for integrations',
            'Priority support',
        ],
        not_included=[
            'A real price jump from Growth — confirm you need biometric/API first',
        ],
    ),
    dict(
        slug='network', name='Network / School Group',
        description='Multi-school, white-label, dedicated schema, SLA',
        base_price=0, included_students=0, max_students=None, price_per_extra_student=500,
        max_users=None, storage_gb=200, sms_bundle=3000,
        billing_interval=Plan.BillingIntervalChoices.ANNUAL, is_self_serve=False,
        included_features=[], not_included=[],
    ),
    dict(
        slug='government', name='Government / EMIS',
        description='Ministry engagement — custom scope and contract',
        base_price=0, included_students=None, max_students=None, price_per_extra_student=0,
        max_users=None, storage_gb=500, sms_bundle=0,
        billing_interval=Plan.BillingIntervalChoices.CUSTOM, is_self_serve=False,
        included_features=[], not_included=[],
    ),
]


class Command(BaseCommand):
    help = 'Seed or update the six Phase 5 subscription plans'

    def handle(self, *args, **options):
        for data in PLANS:
            slug = data.pop('slug')
            plan, created = Plan.objects.update_or_create(slug=slug, defaults=data)
            verb = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(f'{verb}: {plan.name} ({slug})'))

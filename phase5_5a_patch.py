#!/usr/bin/env python3
"""
ASMS Phase 5A patch — Platform Billing & Subscription Engine, data layer only.

What this does:
  1. Creates a new apps/platform_billing/ app: Plan, PlatformInvoice, PlatformPayment.
  2. Adds three fields to Tenant (core/models.py): grace_started_at, suspended_at,
     billing_method — the pieces StatusChoices needs but doesn't have yet.
  3. Adds AllObjectsManager to core/models.py (explicit cross-tenant manager,
     mirroring the one already in apps/student_portal/models.py, promoted to
     core so platform-admin code across apps can share one canonical version).
  4. Registers 'apps.platform_billing' in LOCAL_APPS.

What this does NOT do (later phases):
  - No PesaPal wiring, no IPN handler changes, no Celery tasks (5C/5D).
  - No urls.py entry — nothing to route to yet since there are no views.
  - No migration — run `python manage.py makemigrations platform_billing`
    yourself once this applies cleanly; migrations should come from Django's
    own resolver, not be hand-written.

Every file edit is anchor-guarded: if the exact anchor text isn't found
(file already patched, or hand-edited since the recon paste), that one step
is skipped with a clear message instead of silently corrupting anything.
Safe to re-run — already-applied changes are detected and skipped.

Usage:
    python phase5_5a_patch.py --root /path/to/asms
    python phase5_5a_patch.py              # defaults to current directory
"""
import argparse
import sys
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8')


def patch_file(path: Path, anchor: str, insert_after: str, marker: str, label: str) -> bool:
    """
    Insert `insert_after` right after the first (and required-unique) match
    of `anchor` in `path`, unless `marker` is already present (idempotent).
    Returns True if a change was made.
    """
    if not path.exists():
        print(f'  [SKIP] {label}: {path} does not exist')
        return False

    content = read(path)

    if marker in content:
        print(f'  [OK] {label}: already applied, skipping')
        return False

    count = content.count(anchor)
    if count == 0:
        print(f'  [BLOCKED] {label}: anchor not found in {path}')
        print('            File may have changed since the recon paste. Not touching it.')
        return False
    if count > 1:
        print(f'  [BLOCKED] {label}: anchor found {count} times in {path} (needs to be unique)')
        print('            Not touching it — tell me and I will re-anchor.')
        return False

    new_content = content.replace(anchor, anchor + insert_after, 1)
    write(path, new_content)
    print(f'  [DONE] {label}: patched {path}')
    return True


def create_file_safe(path: Path, content: str, label: str) -> bool:
    if path.exists():
        print(f'  [SKIP] {label}: {path} already exists, not overwriting')
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    write(path, content)
    print(f'  [DONE] {label}: created {path}')
    return True


# ─────────────────────────────────────────────────────────────
# 1. Tenant field additions — apps/core/models.py
# ─────────────────────────────────────────────────────────────

CORE_MODELS_ANCHOR = """    trial_end    = models.DateTimeField(null=True, blank=True)
    plan_end     = models.DateTimeField(null=True, blank=True)"""

CORE_MODELS_INSERT = """

    # Phase 5 — lifecycle timestamps (Section 5.2 / Appendix D.7)
    # grace_started_at / suspended_at let the daily Celery task compute exact
    # day-counts instead of re-deriving them from plan_end each run.
    grace_started_at = models.DateTimeField(null=True, blank=True)
    suspended_at     = models.DateTimeField(null=True, blank=True)

    class BillingMethodChoices(models.TextChoices):
        PESAPAL_CARD  = 'pesapal_card', 'Card (PesaPal, auto-renews)'
        MTN_MOMO      = 'mtn_momo',     'MTN Mobile Money (renewal prompt)'
        AIRTEL_MONEY  = 'airtel',       'Airtel Money (renewal prompt)'
        BANK_TRANSFER = 'bank',         'Bank Transfer (manual)'
        MANUAL        = 'manual',       'Manual / Platform Admin'

    billing_method = models.CharField(
        max_length=20, choices=BillingMethodChoices.choices, blank=True,
        help_text='Which rail this tenant renews through — decides whether the '
                   'daily billing task attempts a silent charge or sends a prompt.'
    )"""

CORE_MODELS_MARKER = 'grace_started_at = models.DateTimeField'

# ─────────────────────────────────────────────────────────────
# 2. AllObjectsManager — end of apps/core/models.py
# ─────────────────────────────────────────────────────────────

MANAGER_ANCHOR = """class TenantManager(models.Manager):
    \"\"\"Automatically filters querysets by the current request tenant.\"\"\"
    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant:
            return qs.filter(tenant=tenant)
        return qs"""

MANAGER_INSERT = """


class AllObjectsManager(models.Manager):
    \"\"\"
    Explicit cross-tenant manager — bypasses the current-tenant filter.
    For platform-admin views only (e.g. the Platform Owner Admin Portal).
    Mirrors the manager already defined locally in apps/student_portal/models.py;
    this is the canonical copy other apps should import going forward.
    \"\"\"
    def get_queryset(self):
        return super().get_queryset()"""

MANAGER_MARKER = 'class AllObjectsManager(models.Manager):'

# ─────────────────────────────────────────────────────────────
# 3. LOCAL_APPS registration — config/settings.py
# ─────────────────────────────────────────────────────────────

SETTINGS_ANCHOR = "    'apps.notifications',"
SETTINGS_INSERT = "\n    'apps.platform_billing',"
SETTINGS_MARKER = "'apps.platform_billing'"

# ─────────────────────────────────────────────────────────────
# 4. New app: apps/platform_billing/
# ─────────────────────────────────────────────────────────────

INIT_PY = ""

APPS_PY = """from django.apps import AppConfig


class PlatformBillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.platform_billing'
    verbose_name = 'Platform Billing & Subscriptions'
"""

MODELS_PY = '''"""
ASMS Platform Billing — Phase 5A (data layer only)

This is ASMS Ltd charging SCHOOLS to use the platform. It is deliberately
separate from apps.finance, which is schools charging THEIR OWN parents —
Section 5 of the spec is explicit that these must never be conflated.

Plan is not tenant-scoped: it's ASMS Ltd's own pricing catalogue, the same
across every tenant. PlatformInvoice snapshots `amount` at issue time so a
future price change never rewrites a historical invoice.

Gateway wiring (PesaPal recurring charges, MoMo/Airtel renewal prompts,
IPN handling) is Phase 5C — not here. PlatformPayment.method already has
the rails Phase 5C will need so this model doesn't move again.
"""
import uuid
from django.db import models
from django.utils import timezone
from apps.core.models import TenantModel


class Plan(models.Model):
    """
    Pricing/limits config for each Tenant.PlanChoices value.
    Kept separate from Tenant so pricing can change without a migration
    touching every tenant row, and so historical invoices can reference
    the plan without inheriting live price changes.
    """
    class BillingIntervalChoices(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        ANNUAL  = 'annual',  'Annual'
        CUSTOM  = 'custom',  'Custom / By Engagement'

    slug = models.CharField(
        max_length=20, unique=True,
        help_text='Must match a Tenant.PlanChoices value exactly (trial/starter/growth/...)'
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)

    base_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    included_students = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Students covered by base_price before price_per_extra_student kicks in'
    )
    max_students = models.PositiveIntegerField(
        null=True, blank=True, help_text='Plan ceiling. Null = no cap (Network/Government).'
    )
    price_per_extra_student = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    max_users = models.PositiveIntegerField(null=True, blank=True, help_text='Null = unlimited')
    storage_gb = models.PositiveIntegerField(default=5)
    sms_bundle = models.PositiveIntegerField(default=0, help_text='SMS units included per period')
    sms_overage_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    billing_interval = models.CharField(
        max_length=10, choices=BillingIntervalChoices.choices,
        default=BillingIntervalChoices.MONTHLY,
    )
    is_active = models.BooleanField(default=True)
    is_self_serve = models.BooleanField(
        default=True,
        help_text='False for Government/EMIS — those go through sales, not self-onboarding'
    )

    class Meta:
        db_table = 'platform_billing_plan'
        ordering = ['base_price']

    def __str__(self):
        return self.name

    def price_for_student_count(self, student_count: int):
        """Base price plus per-student overage beyond included_students."""
        if self.included_students is None or student_count <= self.included_students:
            return self.base_price
        extra = student_count - self.included_students
        return self.base_price + (extra * self.price_per_extra_student)


class PlatformInvoice(TenantModel):
    """One invoice per tenant per billing period. Immutable once ISSUED."""
    class StatusChoices(models.TextChoices):
        DRAFT     = 'draft',     'Draft'
        ISSUED    = 'issued',    'Issued'
        PAID      = 'paid',      'Paid'
        FAILED    = 'failed',    'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    invoice_number = models.CharField(max_length=30, unique=True, blank=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='invoices')

    period_start = models.DateField()
    period_end = models.DateField()
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Snapshot of what was owed for this period — does not change if Plan pricing changes later'
    )
    status = models.CharField(max_length=15, choices=StatusChoices.choices, default=StatusChoices.ISSUED)

    issued_date = models.DateField(default=timezone.now)
    paid_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'platform_billing_invoice'
        ordering = ['-issued_date']

    def __str__(self):
        return f'{self.invoice_number} — {self.tenant.name} — {self.period_start:%b %Y}'

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = f'PLAT-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}'
        super().save(*args, **kwargs)


class PlatformPayment(TenantModel):
    """Immutable payment record settling a PlatformInvoice. One invoice, one payment (no partials)."""
    class MethodChoices(models.TextChoices):
        PESAPAL_CARD  = 'pesapal_card', 'Card (PesaPal)'
        MTN_MOMO      = 'mtn_momo',     'MTN Mobile Money'
        AIRTEL_MONEY  = 'airtel',       'Airtel Money'
        BANK_TRANSFER = 'bank',         'Bank Transfer'
        MANUAL        = 'manual',       'Manual / Platform Admin'

    receipt_number = models.CharField(max_length=30, unique=True, blank=True)
    invoice = models.ForeignKey(PlatformInvoice, on_delete=models.CASCADE, related_name='payments')

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=15, choices=MethodChoices.choices)
    reference = models.CharField(max_length=100, blank=True, help_text='PesaPal order_tracking_id, MoMo ref, etc.')
    is_recurring_charge = models.BooleanField(
        default=False, help_text='True if this came from PesaPal auto-debit rather than a live checkout'
    )
    raw_gateway_response = models.JSONField(default=dict, blank=True)

    payment_date = models.DateField(default=timezone.now)
    recorded_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='platform_payments_recorded'
    )

    class Meta:
        db_table = 'platform_billing_payment'
        ordering = ['-payment_date']

    def __str__(self):
        return f'{self.receipt_number} — {self.invoice.tenant.name} — UGX {self.amount:,.0f}'

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = f'PRCP-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}'
        super().save(*args, **kwargs)
        if self.invoice.status != PlatformInvoice.StatusChoices.PAID:
            self.invoice.status = PlatformInvoice.StatusChoices.PAID
            self.invoice.paid_date = self.payment_date
            self.invoice.save(update_fields=['status', 'paid_date'])
'''

ADMIN_PY = """from django.contrib import admin
from .models import Plan, PlatformInvoice, PlatformPayment


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'base_price', 'billing_interval', 'is_active', 'is_self_serve')
    list_filter = ('billing_interval', 'is_active', 'is_self_serve')
    search_fields = ('name', 'slug')


@admin.register(PlatformInvoice)
class PlatformInvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'tenant', 'plan', 'amount', 'status', 'issued_date', 'paid_date')
    list_filter = ('status', 'plan')
    search_fields = ('invoice_number', 'tenant__name')
    readonly_fields = ('invoice_number',)


@admin.register(PlatformPayment)
class PlatformPaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'invoice', 'amount', 'method', 'is_recurring_charge', 'payment_date')
    list_filter = ('method', 'is_recurring_charge')
    search_fields = ('receipt_number', 'invoice__invoice_number')
    readonly_fields = ('receipt_number',)
"""


SEED_COMMAND_PY = '''"""
Seeds the six Plan rows from the Phase 5 pricing proposal.
Safe to re-run: uses update_or_create keyed on slug, so editing the numbers
below and re-running updates existing rows instead of duplicating them.

    python manage.py seed_plans
"""
from django.core.management.base import BaseCommand
from apps.platform_billing.models import Plan


PLANS = [
    dict(
        slug='trial', name='Free Trial', description='14 days, full feature access, no card required',
        base_price=0, included_students=None, max_students=None, price_per_extra_student=0,
        max_users=None, storage_gb=5, sms_bundle=0,
        billing_interval=Plan.BillingIntervalChoices.CUSTOM, is_self_serve=True,
    ),
    dict(
        slug='starter', name='Starter', description='Small primary school, core operations',
        base_price=150000, included_students=300, max_students=300, price_per_extra_student=0,
        max_users=3, storage_gb=5, sms_bundle=0,
        billing_interval=Plan.BillingIntervalChoices.MONTHLY, is_self_serve=True,
    ),
    dict(
        slug='growth', name='Growth', description='Secondary school, full 28-module platform',
        base_price=350000, included_students=400, max_students=800, price_per_extra_student=400,
        max_users=20, storage_gb=20, sms_bundle=500,
        billing_interval=Plan.BillingIntervalChoices.MONTHLY, is_self_serve=True,
    ),
    dict(
        slug='professional', name='Professional', description='Large school — biometric, API access, unlimited users',
        base_price=700000, included_students=800, max_students=2000, price_per_extra_student=500,
        max_users=None, storage_gb=100, sms_bundle=1500,
        billing_interval=Plan.BillingIntervalChoices.MONTHLY, is_self_serve=True,
    ),
    dict(
        slug='network', name='Network / School Group', description='Multi-school, white-label, dedicated schema, SLA',
        base_price=0, included_students=0, max_students=None, price_per_extra_student=500,
        # UGX 6,000/student/year expressed as a per-student monthly-equivalent rate;
        # actual annual invoicing is a Phase 5C billing_interval=ANNUAL concern.
        max_users=None, storage_gb=200, sms_bundle=3000,
        billing_interval=Plan.BillingIntervalChoices.ANNUAL, is_self_serve=False,
    ),
    dict(
        slug='government', name='Government / EMIS', description='Ministry engagement — custom scope and contract',
        base_price=0, included_students=None, max_students=None, price_per_extra_student=0,
        max_users=None, storage_gb=500, sms_bundle=0,
        billing_interval=Plan.BillingIntervalChoices.CUSTOM, is_self_serve=False,
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
'''


def main():
    parser = argparse.ArgumentParser(description='Apply the ASMS Phase 5A patch')
    parser.add_argument('--root', default='.', help='Project root (contains manage.py)')
    args = parser.parse_args()

    root = Path(args.root).resolve()
    print(f'ASMS Phase 5A patch — root: {root}\n')

    changed = []

    print('1. New app: apps/platform_billing/')
    changed.append(create_file_safe(root / 'apps/platform_billing/__init__.py', INIT_PY, 'platform_billing/__init__.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/apps.py', APPS_PY, 'platform_billing/apps.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/models.py', MODELS_PY, 'platform_billing/models.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/admin.py', ADMIN_PY, 'platform_billing/admin.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/migrations/__init__.py', '', 'platform_billing/migrations/__init__.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/management/__init__.py', '', 'platform_billing/management/__init__.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/management/commands/__init__.py', '', 'platform_billing/management/commands/__init__.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/management/commands/seed_plans.py', SEED_COMMAND_PY, 'platform_billing/management/commands/seed_plans.py'))

    print('\n2. Tenant lifecycle fields + AllObjectsManager: apps/core/models.py')
    changed.append(patch_file(
        root / 'apps/core/models.py', CORE_MODELS_ANCHOR, CORE_MODELS_INSERT,
        CORE_MODELS_MARKER, 'Tenant lifecycle fields'
    ))
    changed.append(patch_file(
        root / 'apps/core/models.py', MANAGER_ANCHOR, MANAGER_INSERT,
        MANAGER_MARKER, 'AllObjectsManager'
    ))

    print('\n3. LOCAL_APPS: config/settings.py')
    changed.append(patch_file(
        root / 'config/settings.py', SETTINGS_ANCHOR, SETTINGS_INSERT,
        SETTINGS_MARKER, 'platform_billing in LOCAL_APPS'
    ))

    print(f'\n{"=" * 60}')
    if any(changed):
        print('Patch applied. Next steps:')
        print('  1. python manage.py makemigrations platform_billing')
        print('  2. python manage.py migrate')
        print('  3. python manage.py seed_plans')
        print('  4. python -m py_compile apps/core/models.py apps/platform_billing/models.py')
    else:
        print('Nothing to do — already applied, or something was blocked (see [BLOCKED] above).')


if __name__ == '__main__':
    main()
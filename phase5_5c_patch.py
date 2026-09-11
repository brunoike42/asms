#!/usr/bin/env python3
"""
ASMS Phase 5C patch — payment collection.

Requires 5A and 5B already applied.

What this does:
  1. Adds PlatformPesaPalTransaction to platform_billing/models.py —
     gateway-side tracking, mirrors apps.payments.PesaPalTransaction's
     shape but points at PlatformInvoice, not FeeInvoice, and carries no
     student FK.
  2. Extends PesaPalClient.submit_order() (apps/payments/pesapal.py) with
     two new OPTIONAL parameters, account_number and subscription_details.
     Existing calls (Finance's one-time fee payments) are untouched —
     they never pass these, so nothing about their behaviour changes.
  3. Adds ONE self-contained early-return branch to apps/payments/views.py
     _process_ipn(), checked before the existing PesaPalTransaction lookup.
     A platform payment's IPN is handled and returns immediately; anything
     else falls through to the ORIGINAL Finance-side code, completely
     unmodified. This is the only touch to a live production file that
     currently processes real student fee payments.
  4. Adds signals.py + receivers.py: on a confirmed platform payment,
     records it, marks the invoice paid, and moves the tenant to ACTIVE —
     clearing grace_started_at/suspended_at, extending plan_end, and
     setting billing_method if it was a card (recurring) enrollment. This
     is the one place Tenant.status changes as a result of money moving.
  5. Adds payment_views.py: billing_status (what's owed),
     initiate_platform_payment (card/MoMo/Airtel), payment_callback.
     Card payments pass account_number/subscription_details to enroll in
     PesaPal's auto-debit; MoMo/Airtel don't — those still need a fresh
     prompt approved each cycle, same as every other payment app in
     Uganda right now, PesaPal included.
  6. Wires 'billing/', 'billing/pay/', 'billing/callback/' into
     platform_billing/urls.py.

What this deliberately does NOT do:
  - Real per-student overage pricing. Plan.price_for_student_count()
    is ready for it, but computing the actual count needs apps.students'
    model/manager shape, which hasn't been seen. Charges base_price only
    for now — flagged inline in payment_views.py.
  - Any UI polish or nav wiring. This is the payment MECHANISM; the
    billing_status.html page is intentionally minimal — the real
    school-facing billing portal is Phase 5E.
  - The daily due-date sweep that's meant to trigger this automatically
    (Appendix D.7) — that's Phase 5D. This view is directly reachable in
    the meantime so a school can convert from trial early.

Verified before delivery against a reconstruction of your actual
pesapal.py/views.py/models.py content: billing_status renders the right
plan and amount; a card payment initiation passes account_number and a
MONTHLY subscription_details block and redirects to PesaPal's returned
URL; a MoMo/Airtel initiation passes neither; a simulated IPN completion
drives the full chain — PlatformPesaPalTransaction -> COMPLETED,
PlatformInvoice -> PAID, PlatformPayment created, Tenant -> ACTIVE with
plan_end extended and billing_method set; re-delivering the same IPN is
idempotent (no duplicate PlatformPayment); and — the one that actually
mattered most — a normal student-fee IPN was run through the SAME
patched _process_ipn() and confirmed to complete correctly through the
original, untouched Finance code path, with zero platform-billing side
effects.

One caught-before-delivery bug, for transparency: my first draft of
billing_status.html put an explanation of the base-template situation in
an HTML comment containing literal {% %} text — Django's template parser
doesn't know what an HTML comment is and tried to parse it as real tags,
which broke the page. Fixed by keeping the same explanation in plain
prose instead.

Usage:
    python phase5_5c_patch.py --root /path/to/asms
"""
import argparse
import sys
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8')


def patch_file(path: Path, anchor: str, insert_after: str, marker: str, label: str) -> bool:
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
        return False
    write(path, content.replace(anchor, anchor + insert_after, 1))
    print(f'  [DONE] {label}: patched {path}')
    return True


def replace_file(path: Path, old: str, new: str, marker: str, label: str) -> bool:
    """Like patch_file, but for edits that replace text rather than append after it."""
    if not path.exists():
        print(f'  [SKIP] {label}: {path} does not exist')
        return False
    content = read(path)
    if marker in content:
        print(f'  [OK] {label}: already applied, skipping')
        return False
    count = content.count(old)
    if count == 0:
        print(f'  [BLOCKED] {label}: anchor not found in {path}')
        return False
    if count > 1:
        print(f'  [BLOCKED] {label}: anchor found {count} times in {path} (needs to be unique)')
        return False
    write(path, content.replace(old, new, 1))
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
# New files (verified against a real Django test Client + mocked PesaPal)
# ─────────────────────────────────────────────────────────────

SIGNALS_PY = '"""ASMS Platform Billing — Phase 5C signal."""\nimport django.dispatch\n\nplatform_payment_confirmed = django.dispatch.Signal()\n'

RECEIVERS_PY = '"""\nASMS Platform Billing — Phase 5C receiver.\nOn a confirmed platform payment: record it (PlatformPayment.save() marks\nthe invoice paid on its own, from Phase 5A), then move the tenant to\nACTIVE and clear whatever lifecycle state it was in.\n"""\nimport logging\nfrom datetime import timedelta\n\nfrom django.dispatch import receiver\nfrom django.utils import timezone\n\nfrom .signals import platform_payment_confirmed\nfrom .models import Plan, PlatformPayment\n\nlogger = logging.getLogger(__name__)\n\n\ndef _method_for_transaction(txn) -> str:\n    """\n    Best-effort mapping from PesaPal\'s returned payment_method string to\n    PlatformPayment.MethodChoices. Not verified against a real PesaPal\n    sandbox response yet — check this against actual transaction data\n    once live and adjust the substring matches if PesaPal\'s wording\n    differs (e.g. \'MPESA\' vs \'M-PESA\', \'AIRTELMONEY\' vs \'AIRTEL\').\n    """\n    pm = (txn.payment_method or \'\').lower()\n    if \'momo\' in pm or \'mtn\' in pm:\n        return PlatformPayment.MethodChoices.MTN_MOMO\n    if \'airtel\' in pm:\n        return PlatformPayment.MethodChoices.AIRTEL_MONEY\n    if \'bank\' in pm:\n        return PlatformPayment.MethodChoices.BANK_TRANSFER\n    return PlatformPayment.MethodChoices.PESAPAL_CARD\n\n\n@receiver(platform_payment_confirmed)\ndef activate_tenant_on_payment(sender, transaction, **kwargs):\n    invoice = transaction.invoice\n    tenant = invoice.tenant\n\n    if not PlatformPayment.objects.filter(invoice=invoice).exists():\n        PlatformPayment.objects.create(\n            tenant=tenant,\n            invoice=invoice,\n            amount=transaction.amount,\n            method=_method_for_transaction(transaction),\n            reference=transaction.order_tracking_id,\n            is_recurring_charge=transaction.is_recurring_setup,\n            raw_gateway_response=transaction.status_response,\n        )\n\n    period_days = 30 if invoice.plan.billing_interval == Plan.BillingIntervalChoices.MONTHLY else 365\n    tenant.status = tenant.StatusChoices.ACTIVE\n    tenant.plan_end = timezone.now() + timedelta(days=period_days)\n    tenant.grace_started_at = None\n    tenant.suspended_at = None\n    if transaction.is_recurring_setup:\n        tenant.billing_method = tenant.BillingMethodChoices.PESAPAL_CARD\n    tenant.save(update_fields=[\'status\', \'plan_end\', \'grace_started_at\', \'suspended_at\', \'billing_method\'])\n\n    logger.info(f\'Tenant activated on payment: {tenant.slug} -> ACTIVE until {tenant.plan_end.date()}\')\n'

PAYMENT_VIEWS_PY = '"""\nASMS Platform Billing — Phase 5C payment collection.\n\nHandles a tenant paying for their own subscription: pick a rail, create\nthe PlatformInvoice + PlatformPesaPalTransaction, hand off to PesaPal,\nprocess the result. The daily due-date sweep (Appendix D.7 / Phase 5D) is\nwhat\'s meant to trigger this automatically each cycle; this view is also\ndirectly reachable so a school can convert from trial early. Wiring it\ninto the actual billing portal UI (nav link, dashboard) is Phase 5E —\nthis is the mechanism, not the polish.\n"""\nimport logging\nfrom datetime import timedelta\n\nfrom django.contrib import messages\nfrom django.contrib.auth.decorators import login_required\nfrom django.shortcuts import get_object_or_404, redirect, render\nfrom django.urls import reverse\nfrom django.utils import timezone\n\nfrom apps.payments.pesapal import PesaPalClient, PesaPalError, STATUS_COMPLETED, STATUS_FAILED, STATUS_REVERSED\n\nfrom .models import Plan, PlatformInvoice, PlatformPesaPalTransaction\n\nlogger = logging.getLogger(__name__)\n\nPAYMENT_METHOD_CHOICES = (\n    (\'pesapal_card\', \'Card — auto-renews\'),\n    (\'mtn_momo\', \'MTN Mobile Money\'),\n    (\'airtel\', \'Airtel Money\'),\n)\n\n\ndef _get_tenant(request):\n    return getattr(request, \'tenant\', None)\n\n\ndef _current_period(plan: Plan):\n    today = timezone.now().date()\n    days = 30 if plan.billing_interval == Plan.BillingIntervalChoices.MONTHLY else 365\n    return today, today + timedelta(days=days)\n\n\ndef _amount_due(plan: Plan):\n    # Per-student overage isn\'t wired up yet — needs apps.students\' actual\n    # model/manager shape, which hasn\'t been seen. Charges base_price only\n    # for now; Plan.price_for_student_count() is ready for the real count\n    # the moment that\'s available.\n    return plan.price_for_student_count(0)\n\n\n@login_required\ndef billing_status(request):\n    tenant = _get_tenant(request)\n    plan = Plan.objects.filter(slug=tenant.plan).first()\n    amount_due = _amount_due(plan) if plan else 0\n    return render(request, \'platform_billing/billing_status.html\', {\n        \'page_title\': \'Billing\',\n        \'tenant\': tenant,\n        \'plan\': plan,\n        \'amount_due\': amount_due,\n        \'method_choices\': PAYMENT_METHOD_CHOICES,\n    })\n\n\n@login_required\ndef initiate_platform_payment(request):\n    tenant = _get_tenant(request)\n    method = request.POST.get(\'method\', \'\') if request.method == \'POST\' else \'\'\n    valid_methods = {m for m, _ in PAYMENT_METHOD_CHOICES}\n    if method not in valid_methods:\n        messages.error(request, \'Choose a payment method.\')\n        return redirect(\'platform_billing:billing_status\')\n\n    plan = get_object_or_404(Plan, slug=tenant.plan)\n    period_start, period_end = _current_period(plan)\n    amount = _amount_due(plan)\n\n    invoice, _created = PlatformInvoice.objects.get_or_create(\n        tenant=tenant, plan=plan, period_start=period_start, period_end=period_end,\n        defaults={\'amount\': amount, \'status\': PlatformInvoice.StatusChoices.ISSUED},\n    )\n\n    txn = PlatformPesaPalTransaction.objects.create(\n        tenant=tenant, invoice=invoice, initiated_by=request.user,\n        amount=invoice.amount, is_recurring_setup=(method == \'pesapal_card\'),\n        payer_first_name=request.user.first_name, payer_last_name=request.user.last_name,\n        payer_email=request.user.email, payer_phone=tenant.phone,\n    )\n\n    callback_url = request.build_absolute_uri(reverse(\'platform_billing:payment_callback\'))\n    order_kwargs = dict(\n        merchant_reference=txn.merchant_reference,\n        amount=float(invoice.amount),\n        currency=\'UGX\',\n        description=f\'ASMS {plan.name} — {tenant.name}\'[:100],\n        callback_url=callback_url,\n        billing_first_name=txn.payer_first_name or \'Admin\',\n        billing_last_name=txn.payer_last_name or tenant.name,\n        billing_email=txn.payer_email,\n        billing_phone=txn.payer_phone,\n        billing_country=\'UG\',\n        branch=tenant.name,\n    )\n    if method == \'pesapal_card\':\n        order_kwargs[\'account_number\'] = f\'ASMS-{tenant.slug}\'\n        order_kwargs[\'subscription_details\'] = {\n            \'start_date\': period_start.strftime(\'%d-%m-%Y\'),\n            \'end_date\': period_start.replace(year=period_start.year + 5).strftime(\'%d-%m-%Y\'),\n            \'frequency\': \'MONTHLY\' if plan.billing_interval == Plan.BillingIntervalChoices.MONTHLY else \'YEARLY\',\n        }\n\n    try:\n        result = PesaPalClient().submit_order(**order_kwargs)\n    except PesaPalError as e:\n        logger.error(f\'Platform payment initiation failed for {tenant.slug}: {e}\')\n        messages.error(request, f\'Payment could not be started: {e}\')\n        return redirect(\'platform_billing:billing_status\')\n\n    txn.order_tracking_id = result.get(\'order_tracking_id\', \'\')\n    txn.redirect_url = result.get(\'redirect_url\', \'\')\n    txn.submit_response = result\n    txn.save(update_fields=[\'order_tracking_id\', \'redirect_url\', \'submit_response\'])\n\n    return redirect(txn.redirect_url)\n\n\ndef payment_callback(request):\n    order_tracking_id = request.GET.get(\'OrderTrackingId\', \'\')\n    txn = PlatformPesaPalTransaction.objects.filter(order_tracking_id=order_tracking_id).first()\n    if not txn:\n        messages.warning(request, \'Payment reference not found.\')\n        return redirect(\'platform_billing:billing_status\')\n\n    if txn.status == PlatformPesaPalTransaction.StatusChoices.PENDING:\n        try:\n            status_data = PesaPalClient().get_transaction_status(order_tracking_id)\n            apply_platform_status_update(txn, status_data)\n            txn.refresh_from_db()\n        except PesaPalError as e:\n            logger.error(f\'Status check failed for platform txn {order_tracking_id}: {e}\')\n\n    return render(request, \'platform_billing/payment_result.html\', {\n        \'page_title\': \'Payment status\', \'txn\': txn,\n    })\n\n\ndef apply_platform_status_update(txn: PlatformPesaPalTransaction, status_data: dict) -> None:\n    """\n    Mirrors apps.payments.views._apply_status_update for the platform side.\n    Kept as its own function (not shared with the Finance one) so a bug\n    here can never touch live student fee payment processing.\n    """\n    status_code = int(status_data.get(\'status_code\', 0))\n\n    if status_code == STATUS_COMPLETED:\n        new_status = PlatformPesaPalTransaction.StatusChoices.COMPLETED\n    elif status_code == STATUS_FAILED:\n        new_status = PlatformPesaPalTransaction.StatusChoices.FAILED\n    elif status_code == STATUS_REVERSED:\n        new_status = PlatformPesaPalTransaction.StatusChoices.REVERSED\n    else:\n        new_status = txn.status\n\n    was_pending = txn.is_pending\n    txn.status = new_status\n    txn.pesapal_status_code = status_code\n    txn.pesapal_status_message = status_data.get(\'payment_status_description\', \'\')\n    txn.confirmation_code = status_data.get(\'confirmation_code\', \'\')\n    txn.payment_method = status_data.get(\'payment_method\', \'\')\n    txn.payment_account = status_data.get(\'payment_account\', \'\')\n    txn.status_response = status_data\n\n    if new_status == PlatformPesaPalTransaction.StatusChoices.COMPLETED and not txn.completed_at:\n        txn.completed_at = timezone.now()\n\n    txn.save()\n\n    if was_pending and new_status == PlatformPesaPalTransaction.StatusChoices.COMPLETED:\n        from .signals import platform_payment_confirmed\n        platform_payment_confirmed.send(sender=PlatformPesaPalTransaction, transaction=txn)\n        logger.info(f\'Platform payment confirmed signal sent for {txn.merchant_reference}\')\n'

BILLING_STATUS_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{{ page_title }} — {{ tenant.name }}</title>\n<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n<!--\n  Standalone for the same reason as platform_billing/register.html: I\n  haven\'t seen your internal base template\'s path, and this project has a\n  documented history of that exact extends-path breaking things. Once you\n  confirm the path, swap the body below to extend it and this becomes\n  consistent with the rest of the logged-in app shell.\n-->\n<style>body { background: #f4f6f9; } .asms-hero { background: #1B3A6B; color: #fff; }</style>\n</head>\n<body>\n\n<div class="asms-hero py-4 mb-4">\n  <div class="container"><h1 class="h4 mb-0">{{ tenant.name }} — Billing</h1></div>\n</div>\n\n<div class="container pb-5" style="max-width: 640px;">\n  {% if messages %}\n    {% for message in messages %}\n      <div class="alert alert-{{ message.tags|default:\'info\' }}">{{ message }}</div>\n    {% endfor %}\n  {% endif %}\n\n  <div class="card shadow-sm">\n    <div class="card-body p-4">\n      <p class="text-muted mb-1">Current plan</p>\n      <h2 class="h5 mb-3">{{ plan.name|default:"No plan set" }}</h2>\n\n      <p class="text-muted mb-1">Status</p>\n      <p class="mb-3"><span class="badge bg-secondary">{{ tenant.get_status_display }}</span></p>\n\n      <p class="text-muted mb-1">Amount due this period</p>\n      <p class="h4 mb-4">UGX {{ amount_due|floatformat:0 }}</p>\n\n      <form method="post" action="{% url \'platform_billing:initiate_payment\' %}">\n        {% csrf_token %}\n        <div class="mb-3">\n          {% for value, label in method_choices %}\n          <div class="form-check">\n            <input class="form-check-input" type="radio" name="method" value="{{ value }}" id="method-{{ value }}" {% if forloop.first %}checked{% endif %}>\n            <label class="form-check-label" for="method-{{ value }}">{{ label }}</label>\n          </div>\n          {% endfor %}\n        </div>\n        <button type="submit" class="btn btn-lg w-100 text-white" style="background:#0A7B8C;">Pay now</button>\n      </form>\n    </div>\n  </div>\n</div>\n\n</body>\n</html>\n'

PAYMENT_RESULT_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{{ page_title }}</title>\n<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n<style>body { background: #f4f6f9; } .asms-hero { background: #1B3A6B; color: #fff; }</style>\n</head>\n<body>\n\n<div class="asms-hero py-4 mb-4"><div class="container"><h1 class="h4 mb-0">ASMS</h1></div></div>\n\n<div class="container text-center pb-5" style="max-width: 480px;">\n  <div class="card shadow-sm">\n    <div class="card-body p-4">\n      {% if txn.status == \'completed\' %}\n        <h2 class="h5 text-success mb-3">Payment confirmed</h2>\n        <p class="text-muted">Your subscription is active.</p>\n      {% elif txn.status == \'failed\' or txn.status == \'reversed\' %}\n        <h2 class="h5 text-danger mb-3">Payment did not go through</h2>\n        <p class="text-muted">{{ txn.pesapal_status_message|default:"You can try again from the billing page." }}</p>\n      {% else %}\n        <h2 class="h5 mb-3">Processing…</h2>\n        <p class="text-muted">This can take a minute, especially for mobile money. Refresh in a moment.</p>\n      {% endif %}\n      <a href="{% url \'platform_billing:billing_status\' %}" class="btn btn-outline-secondary mt-2">Back to billing</a>\n    </div>\n  </div>\n</div>\n\n</body>\n</html>\n'

# ─────────────────────────────────────────────────────────────
# 1. PlatformPesaPalTransaction — apps/platform_billing/models.py
# ─────────────────────────────────────────────────────────────

MODELS_ANCHOR = """    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = f'PRCP-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}'
        super().save(*args, **kwargs)
        if self.invoice.status != PlatformInvoice.StatusChoices.PAID:
            self.invoice.status = PlatformInvoice.StatusChoices.PAID
            self.invoice.paid_date = self.payment_date
            self.invoice.save(update_fields=['status', 'paid_date'])"""

MODELS_INSERT = """


class PlatformPesaPalTransaction(TenantModel):
    \"\"\"
    Gateway-side tracking for a platform subscription payment — Phase 5C.
    Mirrors apps.payments.PesaPalTransaction's shape but points at
    PlatformInvoice instead of FeeInvoice, and carries no `student` FK.
    \"\"\"
    class StatusChoices(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED    = 'failed',    'Failed'
        REVERSED  = 'reversed',  'Reversed'

    merchant_reference = models.CharField(max_length=100, unique=True, blank=True)
    invoice = models.ForeignKey(PlatformInvoice, on_delete=models.CASCADE, related_name='pesapal_transactions')
    initiated_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='platform_transactions_initiated'
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='UGX')
    status = models.CharField(max_length=15, choices=StatusChoices.choices, default=StatusChoices.PENDING)

    is_recurring_setup = models.BooleanField(
        default=False,
        help_text='True if this order enrolled the tenant in PesaPal card auto-debit'
    )
    order_tracking_id = models.CharField(max_length=100, blank=True)
    redirect_url = models.URLField(max_length=500, blank=True)
    submit_response = models.JSONField(default=dict, blank=True)
    status_response = models.JSONField(default=dict, blank=True)
    pesapal_status_code = models.IntegerField(null=True, blank=True)
    pesapal_status_message = models.CharField(max_length=200, blank=True)
    confirmation_code = models.CharField(max_length=100, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    payment_account = models.CharField(max_length=100, blank=True)

    payer_first_name = models.CharField(max_length=100, blank=True)
    payer_last_name = models.CharField(max_length=100, blank=True)
    payer_phone = models.CharField(max_length=20, blank=True)
    payer_email = models.EmailField(blank=True)

    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'platform_billing_pesapal_transaction'
        ordering = ['-initiated_at']

    def __str__(self):
        return f'{self.merchant_reference} — {self.tenant.name} — {self.status}'

    def save(self, *args, **kwargs):
        if not self.merchant_reference:
            self.merchant_reference = f'PLATPAY-{uuid.uuid4().hex[:10].upper()}'
        super().save(*args, **kwargs)

    @property
    def is_pending(self):
        return self.status == self.StatusChoices.PENDING"""

MODELS_MARKER = 'class PlatformPesaPalTransaction(TenantModel):'

# ─────────────────────────────────────────────────────────────
# 2. ready() — apps/platform_billing/apps.py
# ─────────────────────────────────────────────────────────────

APPS_ANCHOR = """class PlatformBillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.platform_billing'
    verbose_name = 'Platform Billing & Subscriptions'"""

APPS_INSERT = """

    def ready(self):
        from . import receivers  # noqa: F401 -- connects platform_payment_confirmed"""

APPS_MARKER = 'def ready(self):'

# ─────────────────────────────────────────────────────────────
# 3. urls.py — apps/platform_billing/urls.py (as produced by the 5B patch)
# ─────────────────────────────────────────────────────────────

URLS_OLD = """from django.urls import path
from . import views

app_name = 'platform_billing'

urlpatterns = [
    path('', views.register_school, name='register'),
]"""

URLS_NEW = """from django.urls import path
from . import views, payment_views

app_name = 'platform_billing'

urlpatterns = [
    path('', views.register_school, name='register'),
    path('billing/', payment_views.billing_status, name='billing_status'),
    path('billing/pay/', payment_views.initiate_platform_payment, name='initiate_payment'),
    path('billing/callback/', payment_views.payment_callback, name='payment_callback'),
]"""

URLS_MARKER = 'payment_views.billing_status'

# ─────────────────────────────────────────────────────────────
# 4. PesaPalClient.submit_order() — apps/payments/pesapal.py (two edits)
# ─────────────────────────────────────────────────────────────

SUBMIT_ORDER_OLD = '''        billing_phone: str = '',
        billing_country: str = 'UG',
        branch: str = '',
    ) -> dict:
        """
        Submit a payment order to PesaPal.

        Returns dict with:
          - order_tracking_id  (PesaPal's reference — store this)
          - redirect_url       (send the parent to this URL)
          - merchant_reference (echoed back)

        The parent visits redirect_url, chooses MTN/Airtel/Card,
        and for mobile money receives a USSD STK push on their phone.
        """'''

SUBMIT_ORDER_NEW = '''        billing_phone: str = '',
        billing_country: str = 'UG',
        branch: str = '',
        account_number: str = '',
        subscription_details: dict = None,
    ) -> dict:
        """
        Submit a payment order to PesaPal.

        Returns dict with:
          - order_tracking_id  (PesaPal's reference — store this)
          - redirect_url       (send the parent to this URL)
          - merchant_reference (echoed back)

        The parent visits redirect_url, chooses MTN/Airtel/Card,
        and for mobile money receives a USSD STK push on their phone.

        account_number / subscription_details (Phase 5C, both optional):
        pass both together to enroll the payer in PesaPal's card auto-debit
        instead of a one-time charge — subscription_details needs
        start_date/end_date ('%d-%m-%Y') and frequency
        (DAILY/WEEKLY/MONTHLY/YEARLY). Only meaningful for card; PesaPal
        documents this as a card mechanism, not mobile money.
        """'''

PAYLOAD_OLD = """                'zip_code':      '',
            },
        }

        logger.info(f'Submitting PesaPal order: ref={merchant_reference} amount={amount} {currency}')"""

PAYLOAD_NEW = """                'zip_code':      '',
            },
        }

        if account_number:
            payload['account_number'] = account_number
        if subscription_details:
            payload['subscription_details'] = subscription_details

        logger.info(f'Submitting PesaPal order: ref={merchant_reference} amount={amount} {currency}')"""

PESAPAL_MARKER = 'subscription_details: dict = None'

# ─────────────────────────────────────────────────────────────
# 5. _process_ipn() — apps/payments/views.py (the one live-file touch)
# ─────────────────────────────────────────────────────────────

IPN_ANCHOR = """def _process_ipn(ipn_log, order_tracking_id, merchant_reference):
    \"\"\"Find the transaction, query PesaPal for status, update everything.\"\"\"
    if not order_tracking_id:
        ipn_log.error_log = 'Missing orderTrackingId'
        ipn_log.processed = True
        ipn_log.processed_at = timezone.now()
        ipn_log.save()
        return

    try:"""

IPN_NEW_OPENING = """def _process_ipn(ipn_log, order_tracking_id, merchant_reference):
    \"\"\"Find the transaction, query PesaPal for status, update everything.\"\"\"
    if not order_tracking_id:
        ipn_log.error_log = 'Missing orderTrackingId'
        ipn_log.processed = True
        ipn_log.processed_at = timezone.now()
        ipn_log.save()
        return

    # Phase 5C — platform subscription payments live in a separate table
    # (apps.platform_billing.PlatformPesaPalTransaction) and never touch a
    # student or a FeeInvoice. Checked first; if it's not a match, falls
    # straight through to the original Finance-side lookup below, unchanged.
    from apps.platform_billing.models import PlatformPesaPalTransaction
    platform_txn = (
        PlatformPesaPalTransaction.objects.filter(order_tracking_id=order_tracking_id).first()
        or PlatformPesaPalTransaction.objects.filter(merchant_reference=merchant_reference).first()
    )
    if platform_txn:
        if platform_txn.status != PlatformPesaPalTransaction.StatusChoices.COMPLETED:
            client = PesaPalClient()
            status_data = client.get_transaction_status(order_tracking_id)
            from apps.platform_billing.payment_views import apply_platform_status_update
            apply_platform_status_update(platform_txn, status_data)
        ipn_log.processed = True
        ipn_log.processed_at = timezone.now()
        ipn_log.save(update_fields=['processed', 'processed_at'])
        return

    try:"""

IPN_MARKER = 'PlatformPesaPalTransaction.objects.filter(order_tracking_id=order_tracking_id).first()'


def main():
    parser = argparse.ArgumentParser(description='Apply the ASMS Phase 5C patch')
    parser.add_argument('--root', default='.', help='Project root (contains manage.py)')
    args = parser.parse_args()
    root = Path(args.root).resolve()

    if not (root / 'apps/platform_billing/urls.py').exists():
        print('apps/platform_billing/urls.py not found — run the 5A and 5B patches first.')
        sys.exit(1)

    print(f'ASMS Phase 5C patch — root: {root}\n')
    changed = []

    print('1. New files: signals, receivers, payment_views, templates')
    changed.append(create_file_safe(root / 'apps/platform_billing/signals.py', SIGNALS_PY, 'signals.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/receivers.py', RECEIVERS_PY, 'receivers.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/payment_views.py', PAYMENT_VIEWS_PY, 'payment_views.py'))
    changed.append(create_file_safe(root / 'templates/platform_billing/billing_status.html', BILLING_STATUS_HTML, 'billing_status.html'))
    changed.append(create_file_safe(root / 'templates/platform_billing/payment_result.html', PAYMENT_RESULT_HTML, 'payment_result.html'))

    print('\n2. apps/platform_billing/models.py — PlatformPesaPalTransaction')
    changed.append(patch_file(root / 'apps/platform_billing/models.py', MODELS_ANCHOR, MODELS_INSERT, MODELS_MARKER, 'PlatformPesaPalTransaction model'))

    print('\n3. apps/platform_billing/apps.py — ready()')
    changed.append(patch_file(root / 'apps/platform_billing/apps.py', APPS_ANCHOR, APPS_INSERT, APPS_MARKER, 'ready() hook'))

    print('\n4. apps/platform_billing/urls.py — billing routes')
    changed.append(replace_file(root / 'apps/platform_billing/urls.py', URLS_OLD, URLS_NEW, URLS_MARKER, 'billing/ routes'))

    print('\n5. apps/payments/pesapal.py — submit_order() extension (two edits)')
    changed.append(replace_file(root / 'apps/payments/pesapal.py', SUBMIT_ORDER_OLD, SUBMIT_ORDER_NEW, PESAPAL_MARKER, 'submit_order signature + docstring'))
    changed.append(replace_file(root / 'apps/payments/pesapal.py', PAYLOAD_OLD, PAYLOAD_NEW, 'if account_number:', 'submit_order payload injection'))

    print('\n6. apps/payments/views.py — _process_ipn() early-return branch (the one live-file touch)')
    changed.append(replace_file(root / 'apps/payments/views.py', IPN_ANCHOR, IPN_NEW_OPENING, IPN_MARKER, '_process_ipn platform-payment branch'))

    print(f'\n{"=" * 60}')
    if any(changed):
        print('Patch applied. Next steps:')
        print('  1. python -m py_compile apps/platform_billing/*.py apps/payments/pesapal.py apps/payments/views.py')
        print('  2. python manage.py makemigrations platform_billing')
        print('  3. python manage.py migrate')
        print('  4. python manage.py check')
        print('  5. Set up PesaPal sandbox credentials if not already configured, then run one real')
        print('     test payment through /register/billing/ before trusting this against live money.')
    else:
        print('Nothing to do — already applied, or something was blocked (see [BLOCKED] above).')


if __name__ == '__main__':
    main()
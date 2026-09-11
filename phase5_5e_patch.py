#!/usr/bin/env python3
"""
ASMS Phase 5E patch — the school billing portal.

Requires 5A through 5D already applied.

What this does:
  1. Adds a small `commas` template filter (new templatetags module) —
     matches the f'{amount:,.0f}' currency display already used in
     apps/finance/models.py's __str__ methods, without assuming
     django.contrib.humanize is in INSTALLED_APPS, which hasn't been
     confirmed either way.
  2. Adds three new pages: invoice_list, invoice_pdf, payment_history —
     the "own subscription, invoices, payment history" from the original
     5A-5F scope.
  3. Adds a shared nav partial (_billing_nav.html) and patches it into
     billing_status.html, so the four billing pages read as one portal
     with tabs instead of four disconnected pages.
  4. Wires the three new routes into platform_billing/urls.py.

The invoice PDF ("School Subscription Invoice" — Section 14's Module
Matrix names this as platform billing's one PDF output) is generated
on demand with WeasyPrint, not generated-once-and-stored-in-Cloudinary
like the other PDF workflows in Appendix D. I haven't confirmed
Cloudinary's exact settings in this project; on-demand is simpler and
still fully correct, just marginally slower on a repeat view of the
same invoice. Swap to store-and-serve later if that matters.

On the "no VAT line" decision: researched before building rather than
guessed at. Uganda's VAT applies to digital services once a business's
annual taxable turnover crosses UGX 150,000,000 — ASMS Ltd is very
unlikely to be near that yet, since Phase 5's whole job has been landing
the *first* paying external school. There's also a proposed 2026
amendment reclassifying software payments as royalties (15% withholding,
a different mechanism from VAT) that's still moving through Parliament,
unsettled as of this search. I'm not a tax advisor and this isn't tax
advice — the invoice has no VAT line for now, but the totals section is
laid out so one slots in without a redesign whenever it's actually owed.
Worth 20 minutes with an accountant before this is collecting real money
at scale, not something I can responsibly settle for you here.

Verified before delivery: rendered a real invoice PDF end to end with
WeasyPrint (not just checked it returns *a* PDF — extracted its text
with pdftotext and confirmed the tenant name, invoice number, PAID
status, payment reference, and comma-formatted amount all actually
landed correctly, and confirmed no VAT line rendered). Also confirmed,
critically: a second tenant's admin sees zero invoices belonging to the
first tenant in the list view, and gets a 404 — not a 403, a 404, so it
doesn't even confirm the invoice ID belongs to someone — trying to fetch
the first tenant's invoice PDF directly by its numeric ID.

Usage:
    python phase5_5e_patch.py --root /path/to/asms
"""
import argparse
import sys
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8')


def replace_file(path: Path, old: str, new: str, marker: str, label: str) -> bool:
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
        print('            File may have changed since the last patch. Not touching it.')
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
# New files (verified against a real Django test Client + real WeasyPrint render)
# ─────────────────────────────────────────────────────────────

TEMPLATETAGS_EXTRAS_PY = '"""\nComma-separated currency display, matching the f\'{amount:,.0f}\' pattern\nalready used in apps/finance/models.py\'s __str__ methods -- kept as our\nown small filter instead of assuming django.contrib.humanize is in\nINSTALLED_APPS, which hasn\'t been confirmed.\n"""\nfrom django import template\n\nregister = template.Library()\n\n\n@register.filter\ndef commas(value):\n    try:\n        return f\'{float(value):,.0f}\'\n    except (TypeError, ValueError):\n        return value\n'

BILLING_NAV_HTML = '<nav class="mb-4">\n  <div class="btn-group" role="group">\n    <a href="{% url \'platform_billing:billing_status\' %}" class="btn btn-sm {% if active_tab == \'overview\' %}btn-secondary{% else %}btn-outline-secondary{% endif %}">Overview</a>\n    <a href="{% url \'platform_billing:invoice_list\' %}" class="btn btn-sm {% if active_tab == \'invoices\' %}btn-secondary{% else %}btn-outline-secondary{% endif %}">Invoices</a>\n    <a href="{% url \'platform_billing:payment_history\' %}" class="btn btn-sm {% if active_tab == \'history\' %}btn-secondary{% else %}btn-outline-secondary{% endif %}">Payment History</a>\n  </div>\n</nav>\n'

INVOICE_LIST_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n{% load platform_billing_extras %}\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{{ page_title }} — {{ tenant.name }}</title>\n<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n<style>body { background: #f4f6f9; } .asms-hero { background: #1B3A6B; color: #fff; }</style>\n</head>\n<body>\n\n<div class="asms-hero py-4 mb-4">\n  <div class="container"><h1 class="h4 mb-0">{{ tenant.name }} — Billing</h1></div>\n</div>\n\n<div class="container pb-5" style="max-width: 800px;">\n  {% include \'platform_billing/_billing_nav.html\' with active_tab=\'invoices\' %}\n\n  <div class="card shadow-sm">\n    <div class="card-body p-4">\n      {% if invoices %}\n      <table class="table align-middle">\n        <thead>\n          <tr>\n            <th>Invoice</th>\n            <th>Period</th>\n            <th>Plan</th>\n            <th>Amount</th>\n            <th>Status</th>\n            <th></th>\n          </tr>\n        </thead>\n        <tbody>\n          {% for invoice in invoices %}\n          <tr>\n            <td>{{ invoice.invoice_number }}</td>\n            <td>{{ invoice.period_start|date:"d M Y" }} – {{ invoice.period_end|date:"d M Y" }}</td>\n            <td>{{ invoice.plan.name }}</td>\n            <td>UGX {{ invoice.amount|commas }}</td>\n            <td>\n              {% if invoice.status == \'paid\' %}<span class="badge bg-success">Paid</span>\n              {% elif invoice.status == \'failed\' %}<span class="badge bg-danger">Failed</span>\n              {% elif invoice.status == \'cancelled\' %}<span class="badge bg-secondary">Cancelled</span>\n              {% else %}<span class="badge bg-warning text-dark">Issued</span>{% endif %}\n            </td>\n            <td><a href="{% url \'platform_billing:invoice_pdf\' pk=invoice.pk %}" target="_blank" class="btn btn-sm btn-outline-secondary">PDF</a></td>\n          </tr>\n          {% endfor %}\n        </tbody>\n      </table>\n      {% else %}\n      <p class="text-muted mb-0">No invoices yet — one is created the first time a payment is started.</p>\n      {% endif %}\n    </div>\n  </div>\n</div>\n\n</body>\n</html>\n'

INVOICE_PDF_HTML = '<!DOCTYPE html>\n<html>\n<head>\n{% load platform_billing_extras %}\n<meta charset="UTF-8">\n<style>\n  @page { size: A4; margin: 2.2cm; }\n  body { font-family: \'DejaVu Sans\', Helvetica, Arial, sans-serif; font-size: 11pt; color: #1a1a1a; }\n  .header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #1B3A6B; padding-bottom: 16px; margin-bottom: 24px; }\n  .brand { font-size: 20pt; font-weight: bold; color: #1B3A6B; }\n  .brand-sub { font-size: 9pt; color: #666; margin-top: 2px; }\n  .invoice-meta { text-align: right; }\n  .invoice-meta .label { font-size: 9pt; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }\n  .invoice-meta .value { font-size: 11pt; margin-bottom: 6px; }\n  .status-badge { display: inline-block; padding: 3px 10px; border-radius: 3px; font-size: 9pt; font-weight: bold; }\n  .status-paid { background: #d1e7dd; color: #0a3622; }\n  .status-issued { background: #fff3cd; color: #664d03; }\n  .status-failed { background: #f8d7da; color: #58151c; }\n  .parties { display: flex; justify-content: space-between; margin-bottom: 28px; }\n  .parties .label { font-size: 9pt; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }\n  table.items { width: 100%; border-collapse: collapse; margin-bottom: 24px; }\n  table.items th { text-align: left; background: #f4f6f9; padding: 8px 10px; font-size: 9pt; text-transform: uppercase; letter-spacing: 0.5px; color: #555; border-bottom: 2px solid #ddd; }\n  table.items td { padding: 10px; border-bottom: 1px solid #eee; }\n  table.items td.amount, table.items th.amount { text-align: right; }\n  .totals { width: 260px; margin-left: auto; }\n  .totals .row { display: flex; justify-content: space-between; padding: 4px 10px; }\n  .totals .row.total { border-top: 2px solid #1B3A6B; font-weight: bold; font-size: 12pt; padding-top: 8px; margin-top: 4px; }\n  .payment-note { background: #f4f6f9; padding: 14px 16px; border-radius: 4px; margin-top: 20px; font-size: 10pt; }\n  .footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid #ddd; font-size: 8.5pt; color: #888; text-align: center; }\n</style>\n</head>\n<body>\n\n<div class="header">\n  <div>\n    <div class="brand">ASMS</div>\n    <div class="brand-sub">Advanced School Management System &middot; ASMS Ltd, Kampala, Uganda</div>\n  </div>\n  <div class="invoice-meta">\n    <div class="label">Invoice</div>\n    <div class="value"><strong>{{ invoice.invoice_number }}</strong></div>\n    <div class="label">Status</div>\n    <div class="value">\n      {% if invoice.status == \'paid\' %}<span class="status-badge status-paid">PAID</span>\n      {% elif invoice.status == \'failed\' %}<span class="status-badge status-failed">FAILED</span>\n      {% else %}<span class="status-badge status-issued">ISSUED</span>{% endif %}\n    </div>\n  </div>\n</div>\n\n<div class="parties">\n  <div>\n    <div class="label">Bill To</div>\n    <div><strong>{{ tenant.name }}</strong></div>\n    {% if tenant.address %}<div>{{ tenant.address }}</div>{% endif %}\n    {% if tenant.district %}<div>{{ tenant.district }}, {{ tenant.country }}</div>{% endif %}\n    {% if tenant.email %}<div>{{ tenant.email }}</div>{% endif %}\n  </div>\n  <div style="text-align: right;">\n    <div class="label">Invoice Date</div>\n    <div>{{ invoice.issued_date|date:"d F Y" }}</div>\n    <div class="label" style="margin-top: 8px;">Billing Period</div>\n    <div>{{ invoice.period_start|date:"d M Y" }} &ndash; {{ invoice.period_end|date:"d M Y" }}</div>\n  </div>\n</div>\n\n<table class="items">\n  <thead>\n    <tr><th>Description</th><th class="amount">Amount (UGX)</th></tr>\n  </thead>\n  <tbody>\n    <tr>\n      <td>\n        ASMS {{ invoice.plan.name }} subscription<br>\n        <span style="color:#888; font-size: 9.5pt;">{{ invoice.period_start|date:"d M Y" }} &ndash; {{ invoice.period_end|date:"d M Y" }}</span>\n      </td>\n      <td class="amount">{{ invoice.amount|commas }}</td>\n    </tr>\n  </tbody>\n</table>\n\n<div class="totals">\n  <div class="row"><span>Subtotal</span><span>UGX {{ invoice.amount|commas }}</span></div>\n  <!-- No VAT line: ASMS Ltd\'s turnover is well under Uganda\'s UGX 150M\n       mandatory VAT registration threshold at this stage. Revisit with\n       an accountant once that changes — this row is where a VAT line\n       would go without needing to redesign the layout. -->\n  <div class="row total"><span>Total Due</span><span>UGX {{ invoice.amount|commas }}</span></div>\n</div>\n\n{% if payment %}\n<div class="payment-note">\n  <strong>Payment received</strong> &mdash; {{ payment.get_method_display }} on {{ payment.payment_date|date:"d F Y" }}\n  {% if payment.reference %}(ref: {{ payment.reference }}){% endif %}. Receipt {{ payment.receipt_number }}.\n</div>\n{% endif %}\n\n<div class="footer">\n  ASMS Ltd &middot; Kampala, Uganda &middot; This is a system-generated invoice for platform subscription fees, separate from any school fees owed by parents.\n</div>\n\n</body>\n</html>\n'

PAYMENT_HISTORY_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n{% load platform_billing_extras %}\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{{ page_title }} — {{ tenant.name }}</title>\n<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n<style>body { background: #f4f6f9; } .asms-hero { background: #1B3A6B; color: #fff; }</style>\n</head>\n<body>\n\n<div class="asms-hero py-4 mb-4">\n  <div class="container"><h1 class="h4 mb-0">{{ tenant.name }} — Billing</h1></div>\n</div>\n\n<div class="container pb-5" style="max-width: 800px;">\n  {% include \'platform_billing/_billing_nav.html\' with active_tab=\'history\' %}\n\n  <div class="card shadow-sm mb-3">\n    <div class="card-body p-4 d-flex justify-content-between">\n      <div>\n        <p class="text-muted mb-1">Total paid</p>\n        <p class="h4 mb-0">UGX {{ stats.total_paid|commas }}</p>\n      </div>\n      <div class="text-end">\n        <p class="text-muted mb-1">Payments</p>\n        <p class="h4 mb-0">{{ stats.count }}</p>\n      </div>\n    </div>\n  </div>\n\n  <div class="card shadow-sm">\n    <div class="card-body p-4">\n      {% if payments %}\n      <table class="table align-middle">\n        <thead>\n          <tr>\n            <th>Receipt</th>\n            <th>Date</th>\n            <th>Method</th>\n            <th>Amount</th>\n            <th>Invoice</th>\n          </tr>\n        </thead>\n        <tbody>\n          {% for payment in payments %}\n          <tr>\n            <td>{{ payment.receipt_number }}</td>\n            <td>{{ payment.payment_date|date:"d M Y" }}</td>\n            <td>{{ payment.get_method_display }}{% if payment.is_recurring_charge %} <span class="badge bg-light text-dark border">auto</span>{% endif %}</td>\n            <td>UGX {{ payment.amount|commas }}</td>\n            <td><a href="{% url \'platform_billing:invoice_pdf\' pk=payment.invoice_id %}" target="_blank">{{ payment.invoice.invoice_number }}</a></td>\n          </tr>\n          {% endfor %}\n        </tbody>\n      </table>\n      {% else %}\n      <p class="text-muted mb-0">No payments yet.</p>\n      {% endif %}\n    </div>\n  </div>\n</div>\n\n</body>\n</html>\n'

# ─────────────────────────────────────────────────────────────
# 1. payment_views.py — header/import update, then three new views
# ─────────────────────────────────────────────────────────────

HEADER_OLD = '''"""
ASMS Platform Billing — Phase 5C payment collection.

Handles a tenant paying for their own subscription: pick a rail, create
the PlatformInvoice + PlatformPesaPalTransaction, hand off to PesaPal,
process the result. The daily due-date sweep (Appendix D.7 / Phase 5D) is
what's meant to trigger this automatically each cycle; this view is also
directly reachable so a school can convert from trial early. Wiring it
into the actual billing portal UI (nav link, dashboard) is Phase 5E —
this is the mechanism, not the polish.
"""
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.payments.pesapal import PesaPalClient, PesaPalError, STATUS_COMPLETED, STATUS_FAILED, STATUS_REVERSED

from .models import Plan, PlatformInvoice, PlatformPesaPalTransaction'''

HEADER_NEW = '''"""
ASMS Platform Billing — Phase 5C/5E payment views.

5C: pick a rail, create the PlatformInvoice + PlatformPesaPalTransaction,
hand off to PesaPal, process the result. 5E (below apply_platform_status_
update): the actual billing portal — invoice list, invoice PDF, payment
history — the pages billing_status.html links out to.
"""
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.payments.pesapal import PesaPalClient, PesaPalError, STATUS_COMPLETED, STATUS_FAILED, STATUS_REVERSED

from .models import Plan, PlatformInvoice, PlatformPayment, PlatformPesaPalTransaction'''

HEADER_MARKER = 'Phase 5C/5E payment views'

TAIL_OLD = '''    if was_pending and new_status == PlatformPesaPalTransaction.StatusChoices.COMPLETED:
        from .signals import platform_payment_confirmed
        platform_payment_confirmed.send(sender=PlatformPesaPalTransaction, transaction=txn)
        logger.info(f'Platform payment confirmed signal sent for {txn.merchant_reference}')'''

TAIL_NEW = TAIL_OLD + '''


# ─────────────────────────────────────────────────────────────
# Phase 5E — school billing portal: invoices + payment history
# ─────────────────────────────────────────────────────────────

@login_required
def invoice_list(request):
    tenant = _get_tenant(request)
    invoices = PlatformInvoice.objects.filter(tenant=tenant).select_related('plan').order_by('-issued_date')
    return render(request, 'platform_billing/invoice_list.html', {
        'page_title': 'Invoices', 'tenant': tenant, 'invoices': invoices,
    })


@login_required
def invoice_pdf(request, pk):
    """
    'School Subscription Invoice' — Section 14's Module Matrix names this
    as platform billing's one PDF output. Generated on demand rather than
    generated-once-and-stored-in-Cloudinary (the pattern the other PDF
    workflows in Appendix D use) — I haven't confirmed Cloudinary's exact
    settings in this project, and on-demand is simpler and still correct;
    swap to store-and-serve later once that's confirmed, for one less
    render on repeat views of the same invoice.
    """
    from weasyprint import HTML
    from django.template.loader import render_to_string
    from django.http import HttpResponse

    tenant = _get_tenant(request)
    invoice = get_object_or_404(PlatformInvoice, pk=pk, tenant=tenant)
    payment = invoice.payments.first()

    html_string = render_to_string('platform_billing/invoice_pdf.html', {
        'invoice': invoice, 'tenant': tenant, 'payment': payment,
    })
    pdf_bytes = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{invoice.invoice_number}.pdf"'
    return response


@login_required
def payment_history(request):
    tenant = _get_tenant(request)
    payments = PlatformPayment.objects.filter(tenant=tenant).select_related('invoice').order_by('-payment_date')
    stats = {
        'total_paid': sum((p.amount for p in payments), start=0),
        'count': payments.count(),
    }
    return render(request, 'platform_billing/payment_history.html', {
        'page_title': 'Payment History', 'tenant': tenant, 'payments': payments, 'stats': stats,
    })'''

TAIL_MARKER = 'def invoice_list(request):'

# ─────────────────────────────────────────────────────────────
# 2. urls.py — three new billing-portal routes
# ─────────────────────────────────────────────────────────────

URLS_OLD = """from django.urls import path
from . import views, payment_views

app_name = 'platform_billing'

urlpatterns = [
    path('', views.register_school, name='register'),
    path('billing/', payment_views.billing_status, name='billing_status'),
    path('billing/pay/', payment_views.initiate_platform_payment, name='initiate_payment'),
    path('billing/callback/', payment_views.payment_callback, name='payment_callback'),
]"""

URLS_NEW = """from django.urls import path
from . import views, payment_views

app_name = 'platform_billing'

urlpatterns = [
    path('', views.register_school, name='register'),
    path('billing/', payment_views.billing_status, name='billing_status'),
    path('billing/pay/', payment_views.initiate_platform_payment, name='initiate_payment'),
    path('billing/callback/', payment_views.payment_callback, name='payment_callback'),
    path('billing/invoices/', payment_views.invoice_list, name='invoice_list'),
    path('billing/invoices/<int:pk>/pdf/', payment_views.invoice_pdf, name='invoice_pdf'),
    path('billing/history/', payment_views.payment_history, name='payment_history'),
]"""

URLS_MARKER = 'name=\'invoice_list\''

# ─────────────────────────────────────────────────────────────
# 3. billing_status.html — nav + comma-formatted amount
# ─────────────────────────────────────────────────────────────

NAV_ANCHOR = """  {% if messages %}
    {% for message in messages %}
      <div class="alert alert-{{ message.tags|default:'info' }}">{{ message }}</div>
    {% endfor %}
  {% endif %}

  <div class="card shadow-sm">"""

NAV_INSERT_BEFORE = """  {% include 'platform_billing/_billing_nav.html' with active_tab='overview' %}

"""

LOAD_ANCHOR = '<meta charset="UTF-8">'
LOAD_INSERT = '\n{% load platform_billing_extras %}'

AMOUNT_OLD = 'UGX {{ amount_due|floatformat:0 }}'
AMOUNT_NEW = 'UGX {{ amount_due|commas }}'

BILLING_STATUS_MARKER = "_billing_nav.html' with active_tab='overview'"


def patch_billing_status(path: Path) -> bool:
    if not path.exists():
        print("  [SKIP] billing_status.html nav/commas: file does not exist")
        return False
    content = read(path)
    if BILLING_STATUS_MARKER in content:
        print('  [OK] billing_status.html nav/commas: already applied, skipping')
        return False
    if NAV_ANCHOR not in content or LOAD_ANCHOR not in content or AMOUNT_OLD not in content:
        print('  [BLOCKED] billing_status.html: one or more anchors not found — file may have changed. Not touching it.')
        return False
    content = content.replace(LOAD_ANCHOR, LOAD_ANCHOR + LOAD_INSERT, 1)
    content = content.replace(NAV_ANCHOR, NAV_INSERT_BEFORE + '  <div class="card shadow-sm">', 1)
    content = content.replace(AMOUNT_OLD, AMOUNT_NEW, 1)
    write(path, content)
    print(f'  [DONE] billing_status.html: nav + comma-formatted amount patched')
    return True


def main():
    parser = argparse.ArgumentParser(description='Apply the ASMS Phase 5E patch')
    parser.add_argument('--root', default='.', help='Project root (contains manage.py)')
    args = parser.parse_args()
    root = Path(args.root).resolve()

    if not (root / 'apps/platform_billing/payment_views.py').exists():
        print('apps/platform_billing/payment_views.py not found — run the 5A-5D patches first.')
        sys.exit(1)

    print(f'ASMS Phase 5E patch — root: {root}\n')
    changed = []

    print('1. New: templatetags filter + three templates')
    changed.append(create_file_safe(root / 'apps/platform_billing/templatetags/__init__.py', '', 'templatetags/__init__.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/templatetags/platform_billing_extras.py', TEMPLATETAGS_EXTRAS_PY, 'platform_billing_extras.py'))
    changed.append(create_file_safe(root / 'templates/platform_billing/_billing_nav.html', BILLING_NAV_HTML, '_billing_nav.html'))
    changed.append(create_file_safe(root / 'templates/platform_billing/invoice_list.html', INVOICE_LIST_HTML, 'invoice_list.html'))
    changed.append(create_file_safe(root / 'templates/platform_billing/invoice_pdf.html', INVOICE_PDF_HTML, 'invoice_pdf.html'))
    changed.append(create_file_safe(root / 'templates/platform_billing/payment_history.html', PAYMENT_HISTORY_HTML, 'payment_history.html'))

    print('\n2. apps/platform_billing/payment_views.py — three new views')
    changed.append(replace_file(root / 'apps/platform_billing/payment_views.py', HEADER_OLD, HEADER_NEW, HEADER_MARKER, 'header + PlatformPayment import'))
    changed.append(replace_file(root / 'apps/platform_billing/payment_views.py', TAIL_OLD, TAIL_NEW, TAIL_MARKER, 'invoice_list / invoice_pdf / payment_history'))

    print('\n3. apps/platform_billing/urls.py — three new routes')
    changed.append(replace_file(root / 'apps/platform_billing/urls.py', URLS_OLD, URLS_NEW, URLS_MARKER, 'invoice/history routes'))

    print('\n4. templates/platform_billing/billing_status.html — shared nav + comma amount')
    changed.append(patch_billing_status(root / 'templates/platform_billing/billing_status.html'))

    print(f'\n{"=" * 60}')
    if any(changed):
        print('Patch applied. Next steps:')
        print('  1. pip install weasyprint   # if not already in requirements.txt')
        print('  2. python -m py_compile apps/platform_billing/*.py apps/platform_billing/templatetags/*.py')
        print('  3. python manage.py check')
        print('  4. Visit /register/billing/invoices/ and download a PDF to eyeball it once yourself')
        print('  5. Twenty minutes with an accountant on the VAT/withholding question before this')
        print('     is collecting real money at any real volume — see the note at the top of this file.')
    else:
        print('Nothing to do — already applied, or something was blocked (see [BLOCKED] above).')


if __name__ == '__main__':
    main()
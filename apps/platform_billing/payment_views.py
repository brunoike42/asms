"""
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

from .models import Plan, PlatformInvoice, PlatformPayment, PlatformPesaPalTransaction

logger = logging.getLogger(__name__)

PAYMENT_METHOD_CHOICES = (
    ('pesapal_card', 'Card — auto-renews'),
    ('mtn_momo', 'MTN Mobile Money'),
    ('airtel', 'Airtel Money'),
)


def _get_tenant(request):
    return getattr(request, 'tenant', None)


def _current_period(plan: Plan):
    today = timezone.now().date()
    days = 30 if plan.billing_interval == Plan.BillingIntervalChoices.MONTHLY else 365
    return today, today + timedelta(days=days)


def _amount_due(plan: Plan, tenant=None):
    # Per-student overage isn't wired up yet — needs apps.students' actual
    # model/manager shape, which hasn't been seen. Charges base_price only
    # for now; Plan.price_for_student_count() is ready for the real count
    # the moment that's available.
    from decimal import Decimal
    amount = plan.price_for_student_count(0)
    if tenant and tenant.discount_percent:
        amount = amount * (Decimal(100 - tenant.discount_percent) / Decimal(100))
    return amount


@login_required
def billing_status(request):
    tenant = _get_tenant(request)
    plan = Plan.objects.filter(slug=tenant.plan).first()
    amount_due = _amount_due(plan, tenant) if plan else 0
    return render(request, 'platform_billing/billing_status.html', {
        'page_title': 'Billing',
        'tenant': tenant,
        'plan': plan,
        'amount_due': amount_due,
        'method_choices': PAYMENT_METHOD_CHOICES,
    })


@login_required
def initiate_platform_payment(request):
    tenant = _get_tenant(request)
    method = request.POST.get('method', '') if request.method == 'POST' else ''
    valid_methods = {m for m, _ in PAYMENT_METHOD_CHOICES}
    if method not in valid_methods:
        messages.error(request, 'Choose a payment method.')
        return redirect('platform_billing:billing_status')

    plan = get_object_or_404(Plan, slug=tenant.plan)
    period_start, period_end = _current_period(plan)
    amount = _amount_due(plan, tenant)

    invoice, _created = PlatformInvoice.objects.get_or_create(
        tenant=tenant, plan=plan, period_start=period_start, period_end=period_end,
        defaults={'amount': amount, 'status': PlatformInvoice.StatusChoices.ISSUED},
    )

    txn = PlatformPesaPalTransaction.objects.create(
        tenant=tenant, invoice=invoice, initiated_by=request.user,
        amount=invoice.amount, is_recurring_setup=(method == 'pesapal_card'),
        payer_first_name=request.user.first_name, payer_last_name=request.user.last_name,
        payer_email=request.user.email, payer_phone=tenant.phone,
    )

    callback_url = request.build_absolute_uri(reverse('platform_billing:payment_callback'))
    order_kwargs = dict(
        merchant_reference=txn.merchant_reference,
        amount=float(invoice.amount),
        currency='UGX',
        description=f'ASMS {plan.name} — {tenant.name}'[:100],
        callback_url=callback_url,
        billing_first_name=txn.payer_first_name or 'Admin',
        billing_last_name=txn.payer_last_name or tenant.name,
        billing_email=txn.payer_email,
        billing_phone=txn.payer_phone,
        billing_country='UG',
        branch=tenant.name,
    )
    if method == 'pesapal_card':
        order_kwargs['account_number'] = f'ASMS-{tenant.slug}'
        order_kwargs['subscription_details'] = {
            'start_date': period_start.strftime('%d-%m-%Y'),
            'end_date': period_start.replace(year=period_start.year + 5).strftime('%d-%m-%Y'),
            'frequency': 'MONTHLY' if plan.billing_interval == Plan.BillingIntervalChoices.MONTHLY else 'YEARLY',
        }

    try:
        result = PesaPalClient().submit_order(**order_kwargs)
    except PesaPalError as e:
        logger.error(f'Platform payment initiation failed for {tenant.slug}: {e}')
        messages.error(request, f'Payment could not be started: {e}')
        return redirect('platform_billing:billing_status')

    txn.order_tracking_id = result.get('order_tracking_id', '')
    txn.redirect_url = result.get('redirect_url', '')
    txn.submit_response = result
    txn.save(update_fields=['order_tracking_id', 'redirect_url', 'submit_response'])

    return redirect(txn.redirect_url)


def payment_callback(request):
    order_tracking_id = request.GET.get('OrderTrackingId', '')
    txn = PlatformPesaPalTransaction.objects.filter(order_tracking_id=order_tracking_id).first()
    if not txn:
        messages.warning(request, 'Payment reference not found.')
        return redirect('platform_billing:billing_status')

    if txn.status == PlatformPesaPalTransaction.StatusChoices.PENDING:
        try:
            status_data = PesaPalClient().get_transaction_status(order_tracking_id)
            apply_platform_status_update(txn, status_data)
            txn.refresh_from_db()
        except PesaPalError as e:
            logger.error(f'Status check failed for platform txn {order_tracking_id}: {e}')

    return render(request, 'platform_billing/payment_result.html', {
        'page_title': 'Payment status', 'txn': txn,
    })


def apply_platform_status_update(txn: PlatformPesaPalTransaction, status_data: dict) -> None:
    """
    Mirrors apps.payments.views._apply_status_update for the platform side.
    Kept as its own function (not shared with the Finance one) so a bug
    here can never touch live student fee payment processing.
    """
    status_code = int(status_data.get('status_code', 0))

    if status_code == STATUS_COMPLETED:
        new_status = PlatformPesaPalTransaction.StatusChoices.COMPLETED
    elif status_code == STATUS_FAILED:
        new_status = PlatformPesaPalTransaction.StatusChoices.FAILED
    elif status_code == STATUS_REVERSED:
        new_status = PlatformPesaPalTransaction.StatusChoices.REVERSED
    else:
        new_status = txn.status

    was_pending = txn.is_pending
    txn.status = new_status
    txn.pesapal_status_code = status_code
    txn.pesapal_status_message = status_data.get('payment_status_description', '')
    txn.confirmation_code = status_data.get('confirmation_code', '')
    txn.payment_method = status_data.get('payment_method', '')
    txn.payment_account = status_data.get('payment_account', '')
    txn.status_response = status_data

    if new_status == PlatformPesaPalTransaction.StatusChoices.COMPLETED and not txn.completed_at:
        txn.completed_at = timezone.now()

    txn.save()

    if was_pending and new_status == PlatformPesaPalTransaction.StatusChoices.COMPLETED:
        from .signals import platform_payment_confirmed
        platform_payment_confirmed.send(sender=PlatformPesaPalTransaction, transaction=txn)
        logger.info(f'Platform payment confirmed signal sent for {txn.merchant_reference}')


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
    })

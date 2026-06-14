"""
PesaPal payment views.

Flow:
  1. Parent/staff clicks Pay → initiate_payment → PesaPal order created
     → parent redirected to PesaPal payment page (STK push or card)
  2. Parent completes payment on PesaPal
  3. PesaPal calls ipn_handler (GET) → we log and process
  4. PesaPal redirects parent to payment_callback
     → we check status and redirect to success/failed page
  5. success_page / failed_page shown to parent

Additionally:
  - check_status (AJAX polling) → used by the processing page
  - payment_history → list of all transactions for a school
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.urls import reverse

from .models import PesaPalTransaction, IPNLog
from .pesapal import PesaPalClient, PesaPalError, STATUS_COMPLETED, STATUS_FAILED, STATUS_REVERSED

logger = logging.getLogger(__name__)


def get_tenant(request):
    return getattr(request, 'tenant', None)


# ──────────────────────────────────────────────────────────────────
#  1. Initiate Payment
# ──────────────────────────────────────────────────────────────────

@login_required
def initiate_payment(request, invoice_pk):
    """
    Display the payment form (phone number + method selection)
    and on POST submit the order to PesaPal.
    """
    from apps.finance.models import FeeInvoice
    tenant = get_tenant(request)
    invoice = get_object_or_404(FeeInvoice, pk=invoice_pk, tenant=tenant)

    # Don't allow re-paying a fully-paid invoice
    if getattr(invoice, 'status', None) == 'paid':
        messages.info(request, 'This invoice is already fully paid.')
        return redirect('finance:invoice_detail', pk=invoice_pk)

    # Calculate outstanding balance
    outstanding = _get_outstanding(invoice)
    if outstanding <= 0:
        messages.info(request, 'Nothing outstanding on this invoice.')
        return redirect('finance:invoice_detail', pk=invoice_pk)

    # Resolve parent/guardian info for pre-filling
    guardian = _get_primary_guardian(invoice.student)

    if request.method == 'POST':
        phone      = request.POST.get('phone', '').strip()
        email      = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        currency   = request.POST.get('currency', 'UGX')

        # Basic validation
        if not phone and not email:
            messages.error(request, 'Please provide a phone number or email address.')
            return _render_pay_form(request, invoice, outstanding, guardian)

        # Build callback URL
        callback_url = request.build_absolute_uri(reverse('payments:callback'))

        # Create a pending transaction record first
        txn = PesaPalTransaction.objects.create(
            tenant           = tenant,
            invoice          = invoice,
            student          = invoice.student,
            initiated_by     = request.user,
            amount           = outstanding,
            currency         = currency,
            payer_first_name = first_name or (guardian.first_name if guardian else ''),
            payer_last_name  = last_name  or (guardian.last_name  if guardian else ''),
            payer_phone      = phone,
            payer_email      = email,
        )

        try:
            client = PesaPalClient()
            result = client.submit_order(
                merchant_reference = txn.merchant_reference,
                amount             = float(outstanding),
                currency           = currency,
                description        = f'School Fees — {invoice.student} — {invoice.pk}',
                callback_url       = callback_url,
                billing_first_name = txn.payer_first_name or 'Parent',
                billing_last_name  = txn.payer_last_name  or 'Guardian',
                billing_email      = email,
                billing_phone      = _format_phone(phone),
                billing_country    = 'UG',
                branch             = tenant.name if hasattr(tenant, 'name') else '',
            )

            # Save PesaPal response to transaction
            txn.order_tracking_id = result.get('order_tracking_id', '')
            txn.redirect_url      = result.get('redirect_url', '')
            txn.submit_response   = result
            txn.save(update_fields=['order_tracking_id', 'redirect_url', 'submit_response'])

            # Redirect parent to PesaPal payment page
            logger.info(
                f'PesaPal order created: {txn.merchant_reference} '
                f'→ tracking {txn.order_tracking_id}'
            )
            return redirect(txn.redirect_url)

        except PesaPalError as e:
            logger.error(f'PesaPal initiation failed for invoice {invoice_pk}: {e}')
            txn.status = PesaPalTransaction.STATUS_FAILED
            txn.save(update_fields=['status'])
            messages.error(request, f'Payment initiation failed: {e}. Please try again.')
            return _render_pay_form(request, invoice, outstanding, guardian)

    return _render_pay_form(request, invoice, outstanding, guardian)


def _render_pay_form(request, invoice, outstanding, guardian):
    context = {
        'page_title': f'Pay Invoice — {invoice.student}',
        'invoice': invoice,
        'outstanding': outstanding,
        'guardian': guardian,
        'sandbox': getattr(__import__('django.conf', fromlist=['settings']).settings, 'PESAPAL_SANDBOX', True),
    }
    return render(request, 'payments/pay.html', context)


# ──────────────────────────────────────────────────────────────────
#  2. PesaPal Callback (parent redirected back after payment)
# ──────────────────────────────────────────────────────────────────

def payment_callback(request):
    """
    PesaPal redirects the parent here after they complete (or abandon) payment.
    Query params: OrderTrackingId, OrderMerchantReference, OrderNotificationType
    We verify the status and redirect to success or failed page.
    """
    order_tracking_id   = request.GET.get('OrderTrackingId', '')
    merchant_reference  = request.GET.get('OrderMerchantReference', '')

    if not order_tracking_id:
        messages.warning(request, 'No payment reference received.')
        return redirect('dashboard')

    # Find the transaction
    try:
        txn = PesaPalTransaction.objects.get(
            order_tracking_id=order_tracking_id,
            merchant_reference=merchant_reference,
        )
    except PesaPalTransaction.DoesNotExist:
        logger.warning(f'Callback received for unknown tracking ID: {order_tracking_id}')
        messages.error(request, 'Transaction not found.')
        return redirect('dashboard')

    # If already processed (IPN arrived first), go straight to result
    if txn.status == PesaPalTransaction.STATUS_COMPLETED:
        return redirect('payments:success', pk=txn.pk)
    if txn.status in (PesaPalTransaction.STATUS_FAILED, PesaPalTransaction.STATUS_REVERSED):
        return redirect('payments:failed', pk=txn.pk)

    # Query PesaPal for live status
    try:
        client = PesaPalClient()
        status_data = client.get_transaction_status(order_tracking_id)
        _apply_status_update(txn, status_data)
    except PesaPalError as e:
        logger.error(f'Status check failed in callback for {order_tracking_id}: {e}')
        # Show processing page — IPN will update when it arrives
        return render(request, 'payments/processing.html', {
            'page_title': 'Processing Payment…',
            'txn': txn,
        })

    if txn.status == PesaPalTransaction.STATUS_COMPLETED:
        return redirect('payments:success', pk=txn.pk)
    elif txn.status in (PesaPalTransaction.STATUS_FAILED, PesaPalTransaction.STATUS_REVERSED):
        return redirect('payments:failed', pk=txn.pk)
    else:
        # Still pending — show processing page with polling
        return render(request, 'payments/processing.html', {
            'page_title': 'Processing Payment…',
            'txn': txn,
        })


# ──────────────────────────────────────────────────────────────────
#  3. PesaPal IPN Handler (server-to-server notification)
# ──────────────────────────────────────────────────────────────────

@csrf_exempt
@require_GET
def ipn_handler(request):
    """
    PesaPal calls this URL (GET) when a payment event occurs.
    We must respond with 200 OK immediately, then process asynchronously.

    Query params:
      orderTrackingId         — PesaPal's tracking ID
      orderMerchantReference  — Our merchant reference
      orderNotificationType   — IPNCHANGE (payment status changed)
    """
    order_tracking_id   = request.GET.get('orderTrackingId', '')
    merchant_reference  = request.GET.get('orderMerchantReference', '')
    notification_type   = request.GET.get('orderNotificationType', '')

    # Log the raw IPN immediately
    ipn_log = IPNLog.objects.create(
        order_tracking_id        = order_tracking_id,
        order_merchant_reference = merchant_reference,
        notification_type        = notification_type,
        raw_query_string         = request.META.get('QUERY_STRING', ''),
    )

    logger.info(
        f'PesaPal IPN received: tracking={order_tracking_id} '
        f'ref={merchant_reference} type={notification_type}'
    )

    # Respond immediately — PesaPal expects a fast 200
    # Process in background (or synchronously here for simplicity)
    try:
        _process_ipn(ipn_log, order_tracking_id, merchant_reference)
    except Exception as e:
        logger.error(f'IPN processing error for {order_tracking_id}: {e}')
        ipn_log.error_log = str(e)
        ipn_log.save(update_fields=['error_log'])

    return HttpResponse('OK', content_type='text/plain', status=200)


def _process_ipn(ipn_log, order_tracking_id, merchant_reference):
    """Find the transaction, query PesaPal for status, update everything."""
    if not order_tracking_id:
        ipn_log.error_log = 'Missing orderTrackingId'
        ipn_log.processed = True
        ipn_log.processed_at = timezone.now()
        ipn_log.save()
        return

    try:
        txn = PesaPalTransaction.objects.get(
            order_tracking_id=order_tracking_id
        )
    except PesaPalTransaction.DoesNotExist:
        # Try by merchant reference as fallback
        try:
            txn = PesaPalTransaction.objects.get(merchant_reference=merchant_reference)
            if not txn.order_tracking_id:
                txn.order_tracking_id = order_tracking_id
                txn.save(update_fields=['order_tracking_id'])
        except PesaPalTransaction.DoesNotExist:
            logger.warning(f'IPN for unknown transaction: {order_tracking_id}')
            ipn_log.error_log = 'Transaction not found'
            ipn_log.processed = True
            ipn_log.processed_at = timezone.now()
            ipn_log.save()
            return

    # Skip if already completed (idempotency)
    if txn.status == PesaPalTransaction.STATUS_COMPLETED:
        ipn_log.processed = True
        ipn_log.processed_at = timezone.now()
        ipn_log.save(update_fields=['processed', 'processed_at'])
        return

    # Get authoritative status from PesaPal
    client = PesaPalClient()
    status_data = client.get_transaction_status(order_tracking_id)
    _apply_status_update(txn, status_data)

    ipn_log.processed    = True
    ipn_log.processed_at = timezone.now()
    ipn_log.save(update_fields=['processed', 'processed_at'])


def _apply_status_update(txn, status_data: dict):
    """
    Apply PesaPal status data to a PesaPalTransaction record.
    Emits the payment_confirmed signal if newly completed.
    """
    status_code = int(status_data.get('status_code', 0))

    if status_code == STATUS_COMPLETED:
        new_status = PesaPalTransaction.STATUS_COMPLETED
    elif status_code == STATUS_FAILED:
        new_status = PesaPalTransaction.STATUS_FAILED
    elif status_code == STATUS_REVERSED:
        new_status = PesaPalTransaction.STATUS_REVERSED
    else:
        new_status = txn.status  # no change

    was_pending = txn.is_pending
    txn.status                 = new_status
    txn.pesapal_status_code    = status_code
    txn.pesapal_status_message = status_data.get('payment_status_description', '')
    txn.confirmation_code      = status_data.get('confirmation_code', '')
    txn.payment_method         = status_data.get('payment_method', '')
    txn.payment_account        = status_data.get('payment_account', '')
    txn.status_response        = status_data

    if new_status == PesaPalTransaction.STATUS_COMPLETED and not txn.completed_at:
        txn.completed_at = timezone.now()

    txn.save()

    # Trigger downstream processing (invoice update, receipt, SMS)
    if was_pending and new_status == PesaPalTransaction.STATUS_COMPLETED:
        from .signals import payment_confirmed
        payment_confirmed.send(sender=PesaPalTransaction, transaction=txn)
        logger.info(f'Payment confirmed signal sent for {txn.merchant_reference}')


# ──────────────────────────────────────────────────────────────────
#  4. AJAX Status Check (used by processing.html polling)
# ──────────────────────────────────────────────────────────────────

@login_required
def check_status(request, pk):
    """
    AJAX endpoint polled by the processing page every 3 seconds.
    Returns JSON: { status, redirect_url }
    """
    tenant = get_tenant(request)
    txn    = get_object_or_404(PesaPalTransaction, pk=pk, tenant=tenant)

    # If still pending, query PesaPal live
    if txn.is_pending:
        try:
            client      = PesaPalClient()
            status_data = client.get_transaction_status(txn.order_tracking_id)
            _apply_status_update(txn, status_data)
            txn.refresh_from_db()
        except PesaPalError:
            pass

    redirect_url = None
    if txn.status == PesaPalTransaction.STATUS_COMPLETED:
        redirect_url = reverse('payments:success', kwargs={'pk': pk})
    elif txn.status in (PesaPalTransaction.STATUS_FAILED, PesaPalTransaction.STATUS_REVERSED):
        redirect_url = reverse('payments:failed', kwargs={'pk': pk})

    return JsonResponse({
        'status':       txn.status,
        'status_label': txn.get_status_display(),
        'redirect_url': redirect_url,
    })


# ──────────────────────────────────────────────────────────────────
#  5. Success / Failed Pages
# ──────────────────────────────────────────────────────────────────

@login_required
def payment_success(request, pk):
    tenant = get_tenant(request)
    txn    = get_object_or_404(PesaPalTransaction, pk=pk, tenant=tenant)
    return render(request, 'payments/success.html', {
        'page_title': 'Payment Confirmed',
        'txn': txn,
    })


@login_required
def payment_failed(request, pk):
    tenant = get_tenant(request)
    txn    = get_object_or_404(PesaPalTransaction, pk=pk, tenant=tenant)
    return render(request, 'payments/failed.html', {
        'page_title': 'Payment Failed',
        'txn': txn,
    })


# ──────────────────────────────────────────────────────────────────
#  6. Payment History
# ──────────────────────────────────────────────────────────────────

@login_required
def payment_history(request):
    from django.core.paginator import Paginator
    tenant = get_tenant(request)
    qs = PesaPalTransaction.objects.filter(tenant=tenant).select_related(
        'student', 'invoice', 'initiated_by'
    ).order_by('-initiated_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator  = Paginator(qs, 25)
    page       = request.GET.get('page', 1)
    txns       = paginator.get_page(page)

    # Summary stats
    from django.db.models import Sum, Count
    stats = {
        'total_collected': qs.filter(
            status=PesaPalTransaction.STATUS_COMPLETED
        ).aggregate(total=Sum('amount'))['total'] or 0,
        'completed_count': qs.filter(status=PesaPalTransaction.STATUS_COMPLETED).count(),
        'pending_count':   qs.filter(status=PesaPalTransaction.STATUS_PENDING).count(),
        'failed_count':    qs.filter(status=PesaPalTransaction.STATUS_FAILED).count(),
    }

    return render(request, 'payments/history.html', {
        'page_title':     'Online Payment History',
        'txns':           txns,
        'stats':          stats,
        'status_choices': PesaPalTransaction.STATUS_CHOICES,
        'status_filter':  status_filter,
    })


# ──────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────

def _get_outstanding(invoice):
    """Return the unpaid balance on an invoice."""
    total_paid = 0
    try:
        total_paid = invoice.payments.filter(
            status__in=['confirmed', 'completed', 'verified']
        ).aggregate(
            total=__import__('django.db.models', fromlist=['Sum']).Sum('amount')
        )['total'] or 0
    except Exception:
        pass
    return max(invoice.total_amount - total_paid, 0)


def _get_primary_guardian(student):
    """Return the primary guardian/parent for pre-filling the form."""
    try:
        return student.guardians.filter(is_primary=True).first() or student.guardians.first()
    except Exception:
        return None


def _format_phone(phone: str) -> str:
    """Normalise a Ugandan phone number to +256XXXXXXXXX format."""
    phone = phone.strip().replace(' ', '').replace('-', '')
    if phone.startswith('0') and len(phone) == 10:
        phone = '+256' + phone[1:]
    elif phone.startswith('256') and not phone.startswith('+'):
        phone = '+' + phone
    elif not phone.startswith('+'):
        phone = '+256' + phone.lstrip('0')
    return phone

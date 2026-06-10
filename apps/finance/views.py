from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Sum, Q
from .models import FeeInvoice, Payment, FeeCategory, FeeStructure
from apps.core.mixins import require_roles


@login_required
@require_roles('school_admin', 'principal', 'accountant')
def invoice_list(request):
    tenant = request.tenant
    status_filter = request.GET.get('status', '')
    qs = FeeInvoice.objects.filter(tenant=tenant).select_related(
        'student', 'term', 'academic_year'
    )
    if status_filter:
        qs = qs.filter(status=status_filter)
    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(
            Q(student__first_name__icontains=q) |
            Q(student__last_name__icontains=q) |
            Q(invoice_number__icontains=q)
        )
    # Summary stats
    stats = {
        'total_invoiced': qs.aggregate(t=Sum('total_amount'))['t'] or 0,
        'total_collected': qs.aggregate(t=Sum('amount_paid'))['t'] or 0,
        'pending_count': qs.filter(status__in=['issued', 'partial', 'overdue']).count(),
    }
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'finance/invoice_list.html', {
        'page_obj': page, 'stats': stats,
        'status_filter': status_filter, 'search_query': q,
        'status_choices': FeeInvoice.StatusChoices.choices,
    })


@login_required
@require_roles('school_admin', 'principal', 'accountant')
def record_payment(request, invoice_pk):
    invoice = get_object_or_404(FeeInvoice, pk=invoice_pk, tenant=request.tenant)
    if request.method == 'POST':
        amount = request.POST.get('amount')
        method = request.POST.get('method')
        reference = request.POST.get('reference', '')
        notes = request.POST.get('notes', '')
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid amount.')
            return redirect('finance:invoice_detail', pk=invoice_pk)
        payment = Payment.objects.create(
            tenant=invoice.tenant,
            invoice=invoice,
            student=invoice.student,
            term=invoice.term,
            amount=amount,
            method=method,
            reference=reference,
            notes=notes,
            recorded_by=request.user,
        )
        messages.success(request, f'Payment of UGX {amount:,.0f} recorded. Receipt: {payment.receipt_number}')
        return redirect('finance:invoice_detail', pk=invoice_pk)
    return redirect('finance:invoice_detail', pk=invoice_pk)


@login_required
@require_roles('school_admin', 'principal', 'accountant')
def invoice_detail(request, pk):
    invoice = get_object_or_404(FeeInvoice, pk=pk, tenant=request.tenant)
    payments = invoice.payments.all().order_by('-payment_date')
    return render(request, 'finance/invoice_detail.html', {
        'invoice': invoice,
        'payments': payments,
        'method_choices': Payment.MethodChoices.choices,
    })

@login_required
def arrears_report(request):
    """Auto-generated stub — implement this view."""
    return render(request, 'core/coming_soon.html', {
        'page_title': 'Arrears Report',
        'message': 'This feature is coming soon.',
    })


@login_required
def generate_invoice(request):
    """Auto-generated stub — implement this view."""
    return render(request, 'core/coming_soon.html', {
        'page_title': 'Generate Invoice',
        'message': 'This feature is coming soon.',
    })


@login_required
def receipt_pdf(request):
    """Auto-generated stub — implement this view."""
    return render(request, 'core/coming_soon.html', {
        'page_title': 'Receipt Pdf',
        'message': 'This feature is coming soon.',
    })

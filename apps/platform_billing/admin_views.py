"""
ASMS Platform Billing — Phase 5F: Platform Owner Admin Portal (Section 5.4).

Every view here is gated by platform_admin_required, not by tenant
matching — this is the one part of the app meant to see across every
tenant. Worth being explicit about why that's safe: Tenant, PlatformInvoice,
PlatformPayment etc. never actually had TenantManager auto-filtering
attached (checked back at 5A — apps/finance's own models don't either;
every view in this whole project filters by tenant explicitly instead of
relying on manager magic). So "querying across tenants" here isn't
bypassing anything — it's just an unfiltered query, same as any other.
What actually needs to be airtight is the role check on every view below.
"""
import logging
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import FeatureFlag, Plan, PlatformInvoice, PlatformPayment

logger = logging.getLogger(__name__)


def platform_admin_required(view_func):
    """@login_required + role check, in that order — an unauthenticated
    request gets sent to login, not a 403 that would leak that the page
    exists at all to someone not logged in."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        from apps.accounts.models import User
        if request.user.role != User.RoleChoices.PLATFORM_ADMIN:
            raise PermissionDenied('Platform admin access required.')
        return view_func(request, *args, **kwargs)
    return wrapper


def _self_serve_slugs():
    return list(Plan.objects.filter(is_self_serve=True).values_list('slug', flat=True))


def _compute_mrr(tenants_qs, plans_by_slug):
    """
    Monthly-equivalent recurring revenue across the given ACTIVE tenants.
    Applies each tenant's manual discount. Does not yet account for
    per-student overage — same known gap as _amount_due in
    payment_views.py, for the same reason (apps.students not seen).
    """
    mrr = Decimal('0')
    for tenant in tenants_qs:
        plan = plans_by_slug.get(tenant.plan)
        if not plan:
            continue
        monthly = plan.base_price if plan.billing_interval == Plan.BillingIntervalChoices.MONTHLY else plan.base_price / 12
        discount_mult = (Decimal(100) - Decimal(tenant.discount_percent)) / Decimal(100)
        mrr += monthly * discount_mult
    return mrr


@platform_admin_required
def dashboard(request):
    from apps.core.models import Tenant

    slugs = _self_serve_slugs()
    self_serve = Tenant.objects.filter(plan__in=slugs)
    active = self_serve.filter(status=Tenant.StatusChoices.ACTIVE)
    plans_by_slug = {p.slug: p for p in Plan.objects.filter(slug__in=slugs)}

    mrr = _compute_mrr(active, plans_by_slug)
    arr = mrr * 12

    total = self_serve.count()
    paid_tenant_ids = PlatformPayment.objects.values_list('tenant_id', flat=True).distinct()
    converted = self_serve.filter(id__in=paid_tenant_ids).count()
    conversion_rate = round(converted / total * 100, 1) if total else 0

    churned = self_serve.filter(status__in=[Tenant.StatusChoices.SUSPENDED, Tenant.StatusChoices.CANCELLED]).count()
    churn_rate = round(churned / total * 100, 1) if total else 0

    by_status = {s.label: self_serve.filter(status=s.value).count() for s in Tenant.StatusChoices}

    return render(request, 'platform_billing/admin_dashboard.html', {
        'page_title': 'Platform Dashboard',
        'mrr': mrr, 'arr': arr,
        'active_count': active.count(), 'total_count': total,
        'conversion_rate': conversion_rate, 'converted': converted,
        'churn_rate': churn_rate, 'churned': churned,
        'by_status': by_status,
    })


@platform_admin_required
def tenant_list(request):
    from apps.core.models import Tenant

    tenants = Tenant.objects.all().order_by('-created_at')

    q = request.GET.get('q', '').strip()
    if q:
        tenants = tenants.filter(name__icontains=q)
    plan = request.GET.get('plan', '')
    if plan:
        tenants = tenants.filter(plan=plan)
    country = request.GET.get('country', '')
    if country:
        tenants = tenants.filter(country=country)
    status = request.GET.get('status', '')
    if status:
        tenants = tenants.filter(status=status)

    paginator = Paginator(tenants, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'platform_billing/admin_tenant_list.html', {
        'page_title': 'Tenants',
        'tenants': page_obj,
        'plans': Plan.objects.all().order_by('base_price'),
        'statuses': Tenant.StatusChoices.choices,
        'countries': Tenant.objects.order_by().values_list('country', flat=True).distinct(),
        'q': q, 'selected_plan': plan, 'selected_country': country, 'selected_status': status,
    })


@platform_admin_required
def tenant_detail(request, pk):
    from apps.core.models import Tenant

    tenant = get_object_or_404(Tenant, pk=pk)
    invoices = PlatformInvoice.objects.filter(tenant=tenant).select_related('plan').order_by('-issued_date')[:10]
    flags = FeatureFlag.objects.filter(tenant=tenant)
    return render(request, 'platform_billing/admin_tenant_detail.html', {
        'page_title': tenant.name,
        'tenant': tenant,
        'invoices': invoices,
        'flags': flags,
        'plans': Plan.objects.filter(is_active=True).order_by('base_price'),
    })


@platform_admin_required
@require_POST
def tenant_extend_trial(request, pk):
    from apps.core.models import Tenant

    tenant = get_object_or_404(Tenant, pk=pk)
    try:
        days = max(1, min(90, int(request.POST.get('days', 7))))
    except ValueError:
        days = 7

    now = timezone.now()
    base = tenant.trial_end if (tenant.trial_end and tenant.trial_end > now) else now
    tenant.trial_end = base + timedelta(days=days)

    # Only revert GRACE_PERIOD -> TRIAL if they landed there via a lapsed
    # trial specifically, not a lapsed renewal. plan_end only ever gets
    # set once a tenant has actually paid at least once (Phase 5C), so an
    # unset plan_end is the signal this tenant never converted.
    if tenant.status == Tenant.StatusChoices.GRACE_PERIOD and not tenant.plan_end:
        tenant.status = Tenant.StatusChoices.TRIAL
        tenant.grace_started_at = None

    tenant.save()
    messages.success(request, f'Trial extended by {days} days, now ends {tenant.trial_end:%d %b %Y}.')
    logger.info(f'{tenant.slug}: trial extended {days}d by {request.user.email}')
    return redirect('platform_admin:tenant_detail', pk=pk)


@platform_admin_required
@require_POST
def tenant_change_plan(request, pk):
    from apps.core.models import Tenant

    tenant = get_object_or_404(Tenant, pk=pk)
    new_slug = request.POST.get('plan', '')
    if not Plan.objects.filter(slug=new_slug).exists():
        messages.error(request, 'Unknown plan.')
        return redirect('platform_admin:tenant_detail', pk=pk)

    old_slug = tenant.plan
    tenant.plan = new_slug
    tenant.save(update_fields=['plan'])
    messages.success(
        request,
        f'Plan changed {old_slug} -> {new_slug}. Takes effect on the next billing cycle — '
        f'a card tenant already enrolled in auto-debit keeps being charged the OLD amount '
        f'until they re-enroll, since PesaPal locked that in at signup, not at each charge.'
    )
    logger.info(f'{tenant.slug}: plan changed {old_slug} -> {new_slug} by {request.user.email}')
    return redirect('platform_admin:tenant_detail', pk=pk)


@platform_admin_required
@require_POST
def tenant_apply_discount(request, pk):
    from apps.core.models import Tenant

    tenant = get_object_or_404(Tenant, pk=pk)
    try:
        pct = int(request.POST.get('discount_percent', 0))
    except ValueError:
        pct = 0
    pct = max(0, min(100, pct))

    tenant.discount_percent = pct
    tenant.save(update_fields=['discount_percent'])
    note = ' (a recurring card tenant\'s next PesaPal auto-debit is already locked in at the old amount — this affects the invoice display and any new manually-started payment, not an in-flight subscription.)' if tenant.billing_method == Tenant.BillingMethodChoices.PESAPAL_CARD else ''
    messages.success(request, f'Discount set to {pct}%.{note}')
    logger.info(f'{tenant.slug}: discount set to {pct}% by {request.user.email}')
    return redirect('platform_admin:tenant_detail', pk=pk)


@platform_admin_required
@require_POST
def tenant_toggle_feature(request, pk):
    from apps.core.models import Tenant

    tenant = get_object_or_404(Tenant, pk=pk)
    module_name = request.POST.get('module_name', '').strip().lower()
    if not module_name:
        messages.error(request, 'Module name required.')
        return redirect('platform_admin:tenant_detail', pk=pk)

    flag, created = FeatureFlag.objects.get_or_create(
        tenant=tenant, module_name=module_name, defaults={'enabled': True}
    )
    if not created:
        flag.enabled = not flag.enabled
        flag.save(update_fields=['enabled'])
    messages.success(request, f'{module_name}: {"enabled" if flag.enabled else "disabled"}.')
    logger.info(f'{tenant.slug}: feature {module_name} -> {flag.enabled} by {request.user.email}')
    return redirect('platform_admin:tenant_detail', pk=pk)


@platform_admin_required
def revenue_report(request):
    from apps.core.models import Tenant

    by_plan = list(
        PlatformPayment.objects.values('invoice__plan__name')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )
    by_country = list(
        PlatformPayment.objects.values('tenant__country')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )
    by_month = list(
        PlatformPayment.objects.annotate(month=TruncMonth('payment_date'))
        .values('month').annotate(total=Sum('amount'), count=Count('id'))
        .order_by('month')
    )

    slugs = _self_serve_slugs()
    active = Tenant.objects.filter(plan__in=slugs, status=Tenant.StatusChoices.ACTIVE)
    plans_by_slug = {p.slug: p for p in Plan.objects.filter(slug__in=slugs)}
    current_mrr = _compute_mrr(active, plans_by_slug)

    # Deliberately naive: current MRR held flat for the next 3 months, not
    # a trend projection. With near-zero payment history so far, a trend
    # line would be fitting noise, not a real growth curve. Revisit once
    # by_month above actually has 6+ real data points to project from.
    forecast = [
        {'months_out': i, 'forecasted_arr': current_mrr * 12}
        for i in (1, 2, 3)
    ]

    return render(request, 'platform_billing/admin_revenue.html', {
        'page_title': 'Revenue',
        'by_plan': by_plan, 'by_country': by_country, 'by_month': by_month,
        'current_mrr': current_mrr, 'forecast': forecast,
    })

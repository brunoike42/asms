#!/usr/bin/env python3
"""
ASMS Phase 5F patch — the Platform Owner Admin Portal (Section 5.4).

Requires 5A through 5E already applied. This closes out the original
5A-5F scope from the start of this phase.

What this does:
  1. Adds FeatureFlag (platform_billing/models.py) and Tenant.discount_
     percent (core/models.py) — the two small schema pieces 5.4 needs
     that nothing earlier in Phase 5 required.
  2. Makes _amount_due (payment_views.py) discount-aware — the one
     cross-cutting change, so a discount a platform admin applies here
     actually flows through to what a school sees on their own billing
     page, not just sits inert on the Tenant record.
  3. Adds admin_views.py + admin_urls.py: dashboard (MRR/ARR/churn proxy/
     conversion rate), a searchable+filterable tenant list, a per-tenant
     detail/drill-in page with four manual actions (extend trial, change
     plan, apply discount, toggle feature flag), and a revenue report
     (by plan / by country / by month, plus a forecast).
  4. Wires 'platform-admin/' into config/urls.py as its own root-level
     include with its own namespace — deliberately NOT nested under the
     existing 'register/' prefix, so these URLs read cleanly
     (/platform-admin/tenants/12/, not /register/platform-admin/...).

On "how does querying across every tenant work here" — worth being
explicit: it doesn't need a bypass. Checked back at 5A: Tenant,
PlatformInvoice, PlatformPayment etc. never actually had TenantManager's
auto-filtering attached as their `objects` manager — matching how
apps/finance's own models work, where every view in this whole project
filters by tenant explicitly rather than relying on manager magic. So an
unfiltered Tenant.objects.all() here isn't bypassing anything that was
ever actually filtering. What has to be airtight instead is the role
check — platform_admin_required is applied to every single view in
admin_views.py, not just the dashboard, and checked accordingly below.

On churn rate and conversion rate: computed as honest proxies from what
this project actually has, not a metric I don't have the data to back.
Conversion = tenants with at least one real PlatformPayment ever, divided
by all self-serve tenants (this needed care — a tenant that lapsed
straight from TRIAL to GRACE_PERIOD without ever paying would be
wrongly counted as "converted" by a naive "not currently TRIAL" check;
using actual payment history avoids that). Churn = tenants currently
SUSPENDED or CANCELLED as a percentage of all self-serve tenants ever
created — a cumulative snapshot, explicitly labeled as such in the UI,
not a monthly cohort rate, since that needs a status-history table this
project doesn't have. Both Network and Government tenants are excluded
from every one of these calculations via Plan.is_self_serve, the same
flag 5B's registration form and 5D's daily sweep already use.

Verified before delivery against a realistic four-tenant scenario (one
active card subscriber who's paid once, one pure trial who's never
paid, one suspended tenant who paid once and then lapsed, one Government
tenant): confirmed the MRR/ARR/conversion/churn numbers come out exactly
right by hand-checking the math against the seed data, confirmed a
Government tenant is invisible to every one of those calculations,
confirmed an unauthenticated request is sent to login rather than shown
a 403 that would leak the page's existence, confirmed a correctly-
authenticated SCHOOL admin (wrong role) gets a 403 on the dashboard AND
on a mutating POST action — not just the landing page — and confirmed,
importantly, the two DIFFERENT trial-extension scenarios: reverting
GRACE_PERIOD back to TRIAL only happens for a tenant that lapsed from an
unpaid trial, never for a paying tenant who lapsed on a renewal, where
extending "trial days" would be meaningless. Also confirmed a discount
applied here actually changes the number on the school's own billing
page, not just a database field nothing reads.

One real limitation, worth knowing rather than discovering later: a
discount applied to a tenant already enrolled in PesaPal card auto-debit
does NOT retroactively change what PesaPal charges on the next cycle —
that amount was locked in at enrollment, and PesaPal debits it without
consulting this app again until the IPN reports the result. The discount
takes effect on the invoice display and on any new manually-started
payment. Message text in tenant_apply_discount() says this plainly when
it applies, but it's a real gap, not just a UI nuance.

Usage:
    python phase5_5f_patch.py --root /path/to/asms
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
# New files (verified against a real Django test Client, real seed data)
# ─────────────────────────────────────────────────────────────

ADMIN_VIEWS_PY = '"""\nASMS Platform Billing — Phase 5F: Platform Owner Admin Portal (Section 5.4).\n\nEvery view here is gated by platform_admin_required, not by tenant\nmatching — this is the one part of the app meant to see across every\ntenant. Worth being explicit about why that\'s safe: Tenant, PlatformInvoice,\nPlatformPayment etc. never actually had TenantManager auto-filtering\nattached (checked back at 5A — apps/finance\'s own models don\'t either;\nevery view in this whole project filters by tenant explicitly instead of\nrelying on manager magic). So "querying across tenants" here isn\'t\nbypassing anything — it\'s just an unfiltered query, same as any other.\nWhat actually needs to be airtight is the role check on every view below.\n"""\nimport logging\nfrom datetime import timedelta\nfrom decimal import Decimal\nfrom functools import wraps\n\nfrom django.contrib import messages\nfrom django.contrib.auth.decorators import login_required\nfrom django.core.exceptions import PermissionDenied\nfrom django.core.paginator import Paginator\nfrom django.db.models import Count, Sum\nfrom django.db.models.functions import TruncMonth\nfrom django.shortcuts import get_object_or_404, redirect, render\nfrom django.utils import timezone\nfrom django.views.decorators.http import require_POST\n\nfrom .models import FeatureFlag, Plan, PlatformInvoice, PlatformPayment\n\nlogger = logging.getLogger(__name__)\n\n\ndef platform_admin_required(view_func):\n    """@login_required + role check, in that order — an unauthenticated\n    request gets sent to login, not a 403 that would leak that the page\n    exists at all to someone not logged in."""\n    @wraps(view_func)\n    @login_required\n    def wrapper(request, *args, **kwargs):\n        from apps.accounts.models import User\n        if request.user.role != User.RoleChoices.PLATFORM_ADMIN:\n            raise PermissionDenied(\'Platform admin access required.\')\n        return view_func(request, *args, **kwargs)\n    return wrapper\n\n\ndef _self_serve_slugs():\n    return list(Plan.objects.filter(is_self_serve=True).values_list(\'slug\', flat=True))\n\n\ndef _compute_mrr(tenants_qs, plans_by_slug):\n    """\n    Monthly-equivalent recurring revenue across the given ACTIVE tenants.\n    Applies each tenant\'s manual discount. Does not yet account for\n    per-student overage — same known gap as _amount_due in\n    payment_views.py, for the same reason (apps.students not seen).\n    """\n    mrr = Decimal(\'0\')\n    for tenant in tenants_qs:\n        plan = plans_by_slug.get(tenant.plan)\n        if not plan:\n            continue\n        monthly = plan.base_price if plan.billing_interval == Plan.BillingIntervalChoices.MONTHLY else plan.base_price / 12\n        discount_mult = (Decimal(100) - Decimal(tenant.discount_percent)) / Decimal(100)\n        mrr += monthly * discount_mult\n    return mrr\n\n\n@platform_admin_required\ndef dashboard(request):\n    from apps.core.models import Tenant\n\n    slugs = _self_serve_slugs()\n    self_serve = Tenant.objects.filter(plan__in=slugs)\n    active = self_serve.filter(status=Tenant.StatusChoices.ACTIVE)\n    plans_by_slug = {p.slug: p for p in Plan.objects.filter(slug__in=slugs)}\n\n    mrr = _compute_mrr(active, plans_by_slug)\n    arr = mrr * 12\n\n    total = self_serve.count()\n    paid_tenant_ids = PlatformPayment.objects.values_list(\'tenant_id\', flat=True).distinct()\n    converted = self_serve.filter(id__in=paid_tenant_ids).count()\n    conversion_rate = round(converted / total * 100, 1) if total else 0\n\n    churned = self_serve.filter(status__in=[Tenant.StatusChoices.SUSPENDED, Tenant.StatusChoices.CANCELLED]).count()\n    churn_rate = round(churned / total * 100, 1) if total else 0\n\n    by_status = {s.label: self_serve.filter(status=s.value).count() for s in Tenant.StatusChoices}\n\n    return render(request, \'platform_billing/admin_dashboard.html\', {\n        \'page_title\': \'Platform Dashboard\',\n        \'mrr\': mrr, \'arr\': arr,\n        \'active_count\': active.count(), \'total_count\': total,\n        \'conversion_rate\': conversion_rate, \'converted\': converted,\n        \'churn_rate\': churn_rate, \'churned\': churned,\n        \'by_status\': by_status,\n    })\n\n\n@platform_admin_required\ndef tenant_list(request):\n    from apps.core.models import Tenant\n\n    tenants = Tenant.objects.all().order_by(\'-created_at\')\n\n    q = request.GET.get(\'q\', \'\').strip()\n    if q:\n        tenants = tenants.filter(name__icontains=q)\n    plan = request.GET.get(\'plan\', \'\')\n    if plan:\n        tenants = tenants.filter(plan=plan)\n    country = request.GET.get(\'country\', \'\')\n    if country:\n        tenants = tenants.filter(country=country)\n    status = request.GET.get(\'status\', \'\')\n    if status:\n        tenants = tenants.filter(status=status)\n\n    paginator = Paginator(tenants, 25)\n    page_obj = paginator.get_page(request.GET.get(\'page\', 1))\n\n    return render(request, \'platform_billing/admin_tenant_list.html\', {\n        \'page_title\': \'Tenants\',\n        \'tenants\': page_obj,\n        \'plans\': Plan.objects.all().order_by(\'base_price\'),\n        \'statuses\': Tenant.StatusChoices.choices,\n        \'countries\': Tenant.objects.order_by().values_list(\'country\', flat=True).distinct(),\n        \'q\': q, \'selected_plan\': plan, \'selected_country\': country, \'selected_status\': status,\n    })\n\n\n@platform_admin_required\ndef tenant_detail(request, pk):\n    from apps.core.models import Tenant\n\n    tenant = get_object_or_404(Tenant, pk=pk)\n    invoices = PlatformInvoice.objects.filter(tenant=tenant).select_related(\'plan\').order_by(\'-issued_date\')[:10]\n    flags = FeatureFlag.objects.filter(tenant=tenant)\n    return render(request, \'platform_billing/admin_tenant_detail.html\', {\n        \'page_title\': tenant.name,\n        \'tenant\': tenant,\n        \'invoices\': invoices,\n        \'flags\': flags,\n        \'plans\': Plan.objects.filter(is_active=True).order_by(\'base_price\'),\n    })\n\n\n@platform_admin_required\n@require_POST\ndef tenant_extend_trial(request, pk):\n    from apps.core.models import Tenant\n\n    tenant = get_object_or_404(Tenant, pk=pk)\n    try:\n        days = max(1, min(90, int(request.POST.get(\'days\', 7))))\n    except ValueError:\n        days = 7\n\n    now = timezone.now()\n    base = tenant.trial_end if (tenant.trial_end and tenant.trial_end > now) else now\n    tenant.trial_end = base + timedelta(days=days)\n\n    # Only revert GRACE_PERIOD -> TRIAL if they landed there via a lapsed\n    # trial specifically, not a lapsed renewal. plan_end only ever gets\n    # set once a tenant has actually paid at least once (Phase 5C), so an\n    # unset plan_end is the signal this tenant never converted.\n    if tenant.status == Tenant.StatusChoices.GRACE_PERIOD and not tenant.plan_end:\n        tenant.status = Tenant.StatusChoices.TRIAL\n        tenant.grace_started_at = None\n\n    tenant.save()\n    messages.success(request, f\'Trial extended by {days} days, now ends {tenant.trial_end:%d %b %Y}.\')\n    logger.info(f\'{tenant.slug}: trial extended {days}d by {request.user.email}\')\n    return redirect(\'platform_admin:tenant_detail\', pk=pk)\n\n\n@platform_admin_required\n@require_POST\ndef tenant_change_plan(request, pk):\n    from apps.core.models import Tenant\n\n    tenant = get_object_or_404(Tenant, pk=pk)\n    new_slug = request.POST.get(\'plan\', \'\')\n    if not Plan.objects.filter(slug=new_slug).exists():\n        messages.error(request, \'Unknown plan.\')\n        return redirect(\'platform_admin:tenant_detail\', pk=pk)\n\n    old_slug = tenant.plan\n    tenant.plan = new_slug\n    tenant.save(update_fields=[\'plan\'])\n    messages.success(\n        request,\n        f\'Plan changed {old_slug} -> {new_slug}. Takes effect on the next billing cycle — \'\n        f\'a card tenant already enrolled in auto-debit keeps being charged the OLD amount \'\n        f\'until they re-enroll, since PesaPal locked that in at signup, not at each charge.\'\n    )\n    logger.info(f\'{tenant.slug}: plan changed {old_slug} -> {new_slug} by {request.user.email}\')\n    return redirect(\'platform_admin:tenant_detail\', pk=pk)\n\n\n@platform_admin_required\n@require_POST\ndef tenant_apply_discount(request, pk):\n    from apps.core.models import Tenant\n\n    tenant = get_object_or_404(Tenant, pk=pk)\n    try:\n        pct = int(request.POST.get(\'discount_percent\', 0))\n    except ValueError:\n        pct = 0\n    pct = max(0, min(100, pct))\n\n    tenant.discount_percent = pct\n    tenant.save(update_fields=[\'discount_percent\'])\n    note = \' (a recurring card tenant\\\'s next PesaPal auto-debit is already locked in at the old amount — this affects the invoice display and any new manually-started payment, not an in-flight subscription.)\' if tenant.billing_method == Tenant.BillingMethodChoices.PESAPAL_CARD else \'\'\n    messages.success(request, f\'Discount set to {pct}%.{note}\')\n    logger.info(f\'{tenant.slug}: discount set to {pct}% by {request.user.email}\')\n    return redirect(\'platform_admin:tenant_detail\', pk=pk)\n\n\n@platform_admin_required\n@require_POST\ndef tenant_toggle_feature(request, pk):\n    from apps.core.models import Tenant\n\n    tenant = get_object_or_404(Tenant, pk=pk)\n    module_name = request.POST.get(\'module_name\', \'\').strip().lower()\n    if not module_name:\n        messages.error(request, \'Module name required.\')\n        return redirect(\'platform_admin:tenant_detail\', pk=pk)\n\n    flag, created = FeatureFlag.objects.get_or_create(\n        tenant=tenant, module_name=module_name, defaults={\'enabled\': True}\n    )\n    if not created:\n        flag.enabled = not flag.enabled\n        flag.save(update_fields=[\'enabled\'])\n    messages.success(request, f\'{module_name}: {"enabled" if flag.enabled else "disabled"}.\')\n    logger.info(f\'{tenant.slug}: feature {module_name} -> {flag.enabled} by {request.user.email}\')\n    return redirect(\'platform_admin:tenant_detail\', pk=pk)\n\n\n@platform_admin_required\ndef revenue_report(request):\n    from apps.core.models import Tenant\n\n    by_plan = list(\n        PlatformPayment.objects.values(\'invoice__plan__name\')\n        .annotate(total=Sum(\'amount\'), count=Count(\'id\'))\n        .order_by(\'-total\')\n    )\n    by_country = list(\n        PlatformPayment.objects.values(\'tenant__country\')\n        .annotate(total=Sum(\'amount\'), count=Count(\'id\'))\n        .order_by(\'-total\')\n    )\n    by_month = list(\n        PlatformPayment.objects.annotate(month=TruncMonth(\'payment_date\'))\n        .values(\'month\').annotate(total=Sum(\'amount\'), count=Count(\'id\'))\n        .order_by(\'month\')\n    )\n\n    slugs = _self_serve_slugs()\n    active = Tenant.objects.filter(plan__in=slugs, status=Tenant.StatusChoices.ACTIVE)\n    plans_by_slug = {p.slug: p for p in Plan.objects.filter(slug__in=slugs)}\n    current_mrr = _compute_mrr(active, plans_by_slug)\n\n    # Deliberately naive: current MRR held flat for the next 3 months, not\n    # a trend projection. With near-zero payment history so far, a trend\n    # line would be fitting noise, not a real growth curve. Revisit once\n    # by_month above actually has 6+ real data points to project from.\n    forecast = [\n        {\'months_out\': i, \'forecasted_arr\': current_mrr * 12}\n        for i in (1, 2, 3)\n    ]\n\n    return render(request, \'platform_billing/admin_revenue.html\', {\n        \'page_title\': \'Revenue\',\n        \'by_plan\': by_plan, \'by_country\': by_country, \'by_month\': by_month,\n        \'current_mrr\': current_mrr, \'forecast\': forecast,\n    })\n'

ADMIN_URLS_PY = "from django.urls import path\nfrom . import admin_views\n\napp_name = 'platform_admin'\n\nurlpatterns = [\n    path('', admin_views.dashboard, name='dashboard'),\n    path('tenants/', admin_views.tenant_list, name='tenant_list'),\n    path('tenants/<int:pk>/', admin_views.tenant_detail, name='tenant_detail'),\n    path('tenants/<int:pk>/extend-trial/', admin_views.tenant_extend_trial, name='tenant_extend_trial'),\n    path('tenants/<int:pk>/change-plan/', admin_views.tenant_change_plan, name='tenant_change_plan'),\n    path('tenants/<int:pk>/discount/', admin_views.tenant_apply_discount, name='tenant_apply_discount'),\n    path('tenants/<int:pk>/toggle-feature/', admin_views.tenant_toggle_feature, name='tenant_toggle_feature'),\n    path('revenue/', admin_views.revenue_report, name='revenue_report'),\n]\n"

ADMIN_DASHBOARD_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n{% load platform_billing_extras %}\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{{ page_title }} — ASMS</title>\n<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n<style>body { background: #f4f6f9; } .asms-hero { background: #1B3A6B; color: #fff; } .stat-card { text-align: center; }</style>\n</head>\n<body>\n\n<div class="asms-hero py-4 mb-4">\n  <div class="container d-flex justify-content-between align-items-center">\n    <h1 class="h4 mb-0">ASMS Platform Admin</h1>\n    <div>\n      <a href="{% url \'platform_admin:tenant_list\' %}" class="btn btn-sm btn-outline-light">Tenants</a>\n      <a href="{% url \'platform_admin:revenue_report\' %}" class="btn btn-sm btn-outline-light">Revenue</a>\n    </div>\n  </div>\n</div>\n\n<div class="container pb-5">\n  {% if messages %}{% for message in messages %}<div class="alert alert-{{ message.tags|default:\'info\' }}">{{ message }}</div>{% endfor %}{% endif %}\n\n  <div class="row g-3 mb-4">\n    <div class="col-md-3"><div class="card shadow-sm stat-card"><div class="card-body">\n      <p class="text-muted mb-1 small">MRR</p><p class="h4 mb-0">UGX {{ mrr|commas }}</p>\n    </div></div></div>\n    <div class="col-md-3"><div class="card shadow-sm stat-card"><div class="card-body">\n      <p class="text-muted mb-1 small">ARR</p><p class="h4 mb-0">UGX {{ arr|commas }}</p>\n    </div></div></div>\n    <div class="col-md-3"><div class="card shadow-sm stat-card"><div class="card-body">\n      <p class="text-muted mb-1 small">Active tenants</p><p class="h4 mb-0">{{ active_count }} <span class="text-muted small">/ {{ total_count }}</span></p>\n    </div></div></div>\n    <div class="col-md-3"><div class="card shadow-sm stat-card"><div class="card-body">\n      <p class="text-muted mb-1 small">Trial conversion</p><p class="h4 mb-0">{{ conversion_rate }}%</p>\n    </div></div></div>\n  </div>\n\n  <div class="row g-3 mb-4">\n    <div class="col-md-6">\n      <div class="card shadow-sm">\n        <div class="card-body">\n          <p class="text-muted mb-1 small">Churn rate <span class="text-muted">(currently suspended/cancelled, as % of ever-onboarded — a simplified proxy, not a monthly cohort rate; that needs a status-history table this project doesn\'t have yet)</span></p>\n          <p class="h5 mb-0">{{ churn_rate }}% <span class="text-muted small">({{ churned }} tenants)</span></p>\n        </div>\n      </div>\n    </div>\n    <div class="col-md-6">\n      <div class="card shadow-sm">\n        <div class="card-body">\n          <p class="text-muted mb-2 small">By status</p>\n          {% for label, count in by_status.items %}\n          <div class="d-flex justify-content-between"><span>{{ label }}</span><span>{{ count }}</span></div>\n          {% endfor %}\n        </div>\n      </div>\n    </div>\n  </div>\n</div>\n\n</body>\n</html>\n'

ADMIN_TENANT_LIST_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{{ page_title }} — ASMS</title>\n<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n<style>body { background: #f4f6f9; } .asms-hero { background: #1B3A6B; color: #fff; }</style>\n</head>\n<body>\n\n<div class="asms-hero py-4 mb-4">\n  <div class="container d-flex justify-content-between align-items-center">\n    <h1 class="h4 mb-0">Tenants</h1>\n    <a href="{% url \'platform_admin:dashboard\' %}" class="btn btn-sm btn-outline-light">Dashboard</a>\n  </div>\n</div>\n\n<div class="container pb-5">\n  <form method="get" class="card shadow-sm mb-3">\n    <div class="card-body p-3">\n      <div class="row g-2">\n        <div class="col-md-4"><input type="text" name="q" value="{{ q }}" placeholder="Search by name" class="form-control form-control-sm"></div>\n        <div class="col-md-2">\n          <select name="plan" class="form-select form-select-sm">\n            <option value="">All plans</option>\n            {% for p in plans %}<option value="{{ p.slug }}" {% if p.slug == selected_plan %}selected{% endif %}>{{ p.name }}</option>{% endfor %}\n          </select>\n        </div>\n        <div class="col-md-2">\n          <select name="status" class="form-select form-select-sm">\n            <option value="">All statuses</option>\n            {% for value, label in statuses %}<option value="{{ value }}" {% if value == selected_status %}selected{% endif %}>{{ label }}</option>{% endfor %}\n          </select>\n        </div>\n        <div class="col-md-2">\n          <select name="country" class="form-select form-select-sm">\n            <option value="">All countries</option>\n            {% for c in countries %}<option value="{{ c }}" {% if c == selected_country %}selected{% endif %}>{{ c }}</option>{% endfor %}\n          </select>\n        </div>\n        <div class="col-md-2"><button type="submit" class="btn btn-sm btn-secondary w-100">Filter</button></div>\n      </div>\n    </div>\n  </form>\n\n  <div class="card shadow-sm">\n    <div class="card-body p-0">\n      <table class="table align-middle mb-0">\n        <thead><tr><th class="ps-3">School</th><th>Plan</th><th>Status</th><th>Country</th><th></th></tr></thead>\n        <tbody>\n          {% for tenant in tenants %}\n          <tr>\n            <td class="ps-3">{{ tenant.name }}</td>\n            <td>{{ tenant.plan }}</td>\n            <td>\n              {% if tenant.status == \'active\' %}<span class="badge bg-success">Active</span>\n              {% elif tenant.status == \'trial\' %}<span class="badge bg-info text-dark">Trial</span>\n              {% elif tenant.status == \'grace_period\' %}<span class="badge bg-warning text-dark">Grace</span>\n              {% elif tenant.status == \'suspended\' %}<span class="badge bg-danger">Suspended</span>\n              {% else %}<span class="badge bg-secondary">{{ tenant.get_status_display }}</span>{% endif %}\n            </td>\n            <td>{{ tenant.country }}</td>\n            <td><a href="{% url \'platform_admin:tenant_detail\' pk=tenant.pk %}" class="btn btn-sm btn-outline-secondary">View</a></td>\n          </tr>\n          {% empty %}\n          <tr><td colspan="5" class="text-muted text-center py-4">No tenants match this filter.</td></tr>\n          {% endfor %}\n        </tbody>\n      </table>\n    </div>\n  </div>\n\n  {% if tenants.has_other_pages %}\n  <nav class="mt-3">\n    <ul class="pagination pagination-sm">\n      {% for num in tenants.paginator.page_range %}\n      <li class="page-item {% if num == tenants.number %}active{% endif %}">\n        <a class="page-link" href="?page={{ num }}&q={{ q }}&plan={{ selected_plan }}&status={{ selected_status }}&country={{ selected_country }}">{{ num }}</a>\n      </li>\n      {% endfor %}\n    </ul>\n  </nav>\n  {% endif %}\n</div>\n\n</body>\n</html>\n'

ADMIN_TENANT_DETAIL_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n{% load platform_billing_extras %}\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{{ page_title }} — ASMS</title>\n<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n<style>body { background: #f4f6f9; } .asms-hero { background: #1B3A6B; color: #fff; }</style>\n</head>\n<body>\n\n<div class="asms-hero py-4 mb-4">\n  <div class="container d-flex justify-content-between align-items-center">\n    <h1 class="h4 mb-0">{{ tenant.name }}</h1>\n    <a href="{% url \'platform_admin:tenant_list\' %}" class="btn btn-sm btn-outline-light">Back to tenants</a>\n  </div>\n</div>\n\n<div class="container pb-5">\n  {% if messages %}{% for message in messages %}<div class="alert alert-{{ message.tags|default:\'info\' }}">{{ message }}</div>{% endfor %}{% endif %}\n\n  <div class="row g-3 mb-3">\n    <div class="col-md-3"><div class="card shadow-sm"><div class="card-body"><p class="text-muted small mb-1">Plan</p><p class="mb-0">{{ tenant.plan }}</p></div></div></div>\n    <div class="col-md-3"><div class="card shadow-sm"><div class="card-body"><p class="text-muted small mb-1">Status</p><p class="mb-0">{{ tenant.get_status_display }}</p></div></div></div>\n    <div class="col-md-3"><div class="card shadow-sm"><div class="card-body"><p class="text-muted small mb-1">Billing method</p><p class="mb-0">{{ tenant.get_billing_method_display|default:"Not set" }}</p></div></div></div>\n    <div class="col-md-3"><div class="card shadow-sm"><div class="card-body"><p class="text-muted small mb-1">Discount</p><p class="mb-0">{{ tenant.discount_percent }}%</p></div></div></div>\n  </div>\n\n  <div class="row g-3">\n    <div class="col-md-6">\n      <div class="card shadow-sm mb-3">\n        <div class="card-body">\n          <h2 class="h6">Extend trial</h2>\n          <form method="post" action="{% url \'platform_admin:tenant_extend_trial\' pk=tenant.pk %}" class="d-flex gap-2">\n            {% csrf_token %}\n            <input type="number" name="days" value="7" min="1" max="90" class="form-control form-control-sm" style="width:80px">\n            <button type="submit" class="btn btn-sm btn-secondary">Extend (days)</button>\n          </form>\n        </div>\n      </div>\n\n      <div class="card shadow-sm mb-3">\n        <div class="card-body">\n          <h2 class="h6">Change plan</h2>\n          <form method="post" action="{% url \'platform_admin:tenant_change_plan\' pk=tenant.pk %}" class="d-flex gap-2">\n            {% csrf_token %}\n            <select name="plan" class="form-select form-select-sm">\n              {% for p in plans %}<option value="{{ p.slug }}" {% if p.slug == tenant.plan %}selected{% endif %}>{{ p.name }}</option>{% endfor %}\n            </select>\n            <button type="submit" class="btn btn-sm btn-secondary">Change</button>\n          </form>\n        </div>\n      </div>\n\n      <div class="card shadow-sm mb-3">\n        <div class="card-body">\n          <h2 class="h6">Apply discount</h2>\n          <form method="post" action="{% url \'platform_admin:tenant_apply_discount\' pk=tenant.pk %}" class="d-flex gap-2">\n            {% csrf_token %}\n            <input type="number" name="discount_percent" value="{{ tenant.discount_percent }}" min="0" max="100" class="form-control form-control-sm" style="width:80px">\n            <span class="align-self-center">%</span>\n            <button type="submit" class="btn btn-sm btn-secondary">Set</button>\n          </form>\n        </div>\n      </div>\n\n      <div class="card shadow-sm">\n        <div class="card-body">\n          <h2 class="h6">Feature flags</h2>\n          {% for flag in flags %}\n          <div class="d-flex justify-content-between align-items-center mb-1">\n            <span>{{ flag.module_name }} — {% if flag.enabled %}<span class="text-success">on</span>{% else %}<span class="text-danger">off</span>{% endif %}</span>\n            <form method="post" action="{% url \'platform_admin:tenant_toggle_feature\' pk=tenant.pk %}">\n              {% csrf_token %}\n              <input type="hidden" name="module_name" value="{{ flag.module_name }}">\n              <button type="submit" class="btn btn-sm btn-outline-secondary">Toggle</button>\n            </form>\n          </div>\n          {% endfor %}\n          <form method="post" action="{% url \'platform_admin:tenant_toggle_feature\' pk=tenant.pk %}" class="d-flex gap-2 mt-2">\n            {% csrf_token %}\n            <input type="text" name="module_name" placeholder="module name" class="form-control form-control-sm">\n            <button type="submit" class="btn btn-sm btn-secondary">Add / toggle</button>\n          </form>\n        </div>\n      </div>\n    </div>\n\n    <div class="col-md-6">\n      <div class="card shadow-sm">\n        <div class="card-body">\n          <h2 class="h6">Recent invoices</h2>\n          <table class="table table-sm">\n            <thead><tr><th>Invoice</th><th>Amount</th><th>Status</th></tr></thead>\n            <tbody>\n              {% for invoice in invoices %}\n              <tr><td>{{ invoice.invoice_number }}</td><td>UGX {{ invoice.amount|commas }}</td><td>{{ invoice.get_status_display }}</td></tr>\n              {% empty %}\n              <tr><td colspan="3" class="text-muted">No invoices yet.</td></tr>\n              {% endfor %}\n            </tbody>\n          </table>\n        </div>\n      </div>\n    </div>\n  </div>\n</div>\n\n</body>\n</html>\n'

ADMIN_REVENUE_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n{% load platform_billing_extras %}\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{{ page_title }} — ASMS</title>\n<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n<style>body { background: #f4f6f9; } .asms-hero { background: #1B3A6B; color: #fff; }</style>\n</head>\n<body>\n\n<div class="asms-hero py-4 mb-4">\n  <div class="container d-flex justify-content-between align-items-center">\n    <h1 class="h4 mb-0">Revenue</h1>\n    <a href="{% url \'platform_admin:dashboard\' %}" class="btn btn-sm btn-outline-light">Dashboard</a>\n  </div>\n</div>\n\n<div class="container pb-5">\n  <div class="row g-3 mb-4">\n    <div class="col-md-4">\n      <div class="card shadow-sm"><div class="card-body">\n        <h2 class="h6">By plan</h2>\n        <table class="table table-sm mb-0">\n          {% for row in by_plan %}<tr><td>{{ row.invoice__plan__name|default:"—" }}</td><td class="text-end">UGX {{ row.total|commas }}</td></tr>{% empty %}<tr><td class="text-muted">No payments yet.</td></tr>{% endfor %}\n        </table>\n      </div></div>\n    </div>\n    <div class="col-md-4">\n      <div class="card shadow-sm"><div class="card-body">\n        <h2 class="h6">By country</h2>\n        <table class="table table-sm mb-0">\n          {% for row in by_country %}<tr><td>{{ row.tenant__country|default:"—" }}</td><td class="text-end">UGX {{ row.total|commas }}</td></tr>{% empty %}<tr><td class="text-muted">No payments yet.</td></tr>{% endfor %}\n        </table>\n      </div></div>\n    </div>\n    <div class="col-md-4">\n      <div class="card shadow-sm"><div class="card-body">\n        <h2 class="h6">By month</h2>\n        <table class="table table-sm mb-0">\n          {% for row in by_month %}<tr><td>{{ row.month|date:"M Y" }}</td><td class="text-end">UGX {{ row.total|commas }}</td></tr>{% empty %}<tr><td class="text-muted">No payments yet.</td></tr>{% endfor %}\n        </table>\n      </div></div>\n    </div>\n  </div>\n\n  <div class="card shadow-sm">\n    <div class="card-body">\n      <h2 class="h6">Forecast <span class="text-muted small">— current MRR held flat, not a growth trend. There isn\'t enough payment history yet for a trend to mean anything; this updates into a real projection once by-month above has several real data points.</span></h2>\n      <table class="table table-sm mb-0">\n        <thead><tr><th>Months out</th><th class="text-end">Forecasted ARR</th></tr></thead>\n        <tbody>\n          {% for row in forecast %}<tr><td>+{{ row.months_out }}</td><td class="text-end">UGX {{ row.forecasted_arr|commas }}</td></tr>{% endfor %}\n        </tbody>\n      </table>\n    </div>\n  </div>\n</div>\n\n</body>\n</html>\n'

# ─────────────────────────────────────────────────────────────
# 1. FeatureFlag — apps/platform_billing/models.py
# ─────────────────────────────────────────────────────────────

MODELS_ANCHOR = """    def save(self, *args, **kwargs):
        if not self.merchant_reference:
            self.merchant_reference = f'PLATPAY-{uuid.uuid4().hex[:10].upper()}'
        super().save(*args, **kwargs)

    @property
    def is_pending(self):
        return self.status == self.StatusChoices.PENDING"""

MODELS_INSERT = """


class FeatureFlag(TenantModel):
    \"\"\"Per-tenant module enable/disable — Section 5.4's feature flag management.\"\"\"
    module_name = models.CharField(max_length=50, help_text="e.g. 'lms', 'biometric_attendance', 'career_guidance'")
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'platform_billing_feature_flag'
        unique_together = [('tenant', 'module_name')]
        ordering = ['module_name']

    def __str__(self):
        return f'{self.tenant.name} — {self.module_name}: {"on" if self.enabled else "off"}'"""

MODELS_MARKER = 'class FeatureFlag(TenantModel):'

# ─────────────────────────────────────────────────────────────
# 2. Tenant.discount_percent — apps/core/models.py
# ─────────────────────────────────────────────────────────────

CORE_OLD = """    billing_method = models.CharField(
        max_length=20, choices=BillingMethodChoices.choices, blank=True,
        help_text='Which rail this tenant renews through — decides whether the '
                   'daily billing task attempts a silent charge or sends a prompt.'
    )
    deletion_warning_sent_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Set once, the first time the 60-day suspension deletion warning '
                   'goes out — stops the daily sweep re-sending it every day after.'
    )"""

CORE_NEW = CORE_OLD + """
    discount_percent = models.PositiveSmallIntegerField(
        default=0,
        help_text='Manual discount (0-100) applied by a platform admin — Section 5.4.'
    )"""

CORE_MARKER = 'discount_percent = models.PositiveSmallIntegerField'

# ─────────────────────────────────────────────────────────────
# 3. _amount_due discount-awareness — apps/platform_billing/payment_views.py
# ─────────────────────────────────────────────────────────────

AMOUNT_DUE_OLD = """def _amount_due(plan: Plan):
    # Per-student overage isn't wired up yet — needs apps.students' actual
    # model/manager shape, which hasn't been seen. Charges base_price only
    # for now; Plan.price_for_student_count() is ready for the real count
    # the moment that's available.
    return plan.price_for_student_count(0)"""

AMOUNT_DUE_NEW = """def _amount_due(plan: Plan, tenant=None):
    # Per-student overage isn't wired up yet — needs apps.students' actual
    # model/manager shape, which hasn't been seen. Charges base_price only
    # for now; Plan.price_for_student_count() is ready for the real count
    # the moment that's available.
    from decimal import Decimal
    amount = plan.price_for_student_count(0)
    if tenant and tenant.discount_percent:
        amount = amount * (Decimal(100 - tenant.discount_percent) / Decimal(100))
    return amount"""

AMOUNT_DUE_MARKER = 'def _amount_due(plan: Plan, tenant=None):'

CALL_SITE_1_OLD = '    amount_due = _amount_due(plan) if plan else 0'
CALL_SITE_1_NEW = '    amount_due = _amount_due(plan, tenant) if plan else 0'
CALL_SITE_1_MARKER = '_amount_due(plan, tenant) if plan'

CALL_SITE_2_OLD = '    amount = _amount_due(plan)'
CALL_SITE_2_NEW = '    amount = _amount_due(plan, tenant)'
CALL_SITE_2_MARKER = 'amount = _amount_due(plan, tenant)'

# ─────────────────────────────────────────────────────────────
# 4. config/urls.py — platform-admin/ root include
# ─────────────────────────────────────────────────────────────

URLS_ANCHOR = "\n    path('register/', include('apps.platform_billing.urls', namespace='platform_billing')),"
URLS_INSERT = "\n    path('platform-admin/', include('apps.platform_billing.admin_urls', namespace='platform_admin')),"
URLS_MARKER = "namespace='platform_admin'"


def main():
    parser = argparse.ArgumentParser(description='Apply the ASMS Phase 5F patch')
    parser.add_argument('--root', default='.', help='Project root (contains manage.py)')
    args = parser.parse_args()
    root = Path(args.root).resolve()

    if not (root / 'apps/platform_billing/payment_views.py').exists():
        print('apps/platform_billing/payment_views.py not found — run the 5A-5E patches first.')
        sys.exit(1)

    print(f'ASMS Phase 5F patch — root: {root}\n')
    changed = []

    print('1. New: admin_views.py, admin_urls.py, four templates')
    changed.append(create_file_safe(root / 'apps/platform_billing/admin_views.py', ADMIN_VIEWS_PY, 'admin_views.py'))
    changed.append(create_file_safe(root / 'apps/platform_billing/admin_urls.py', ADMIN_URLS_PY, 'admin_urls.py'))
    changed.append(create_file_safe(root / 'templates/platform_billing/admin_dashboard.html', ADMIN_DASHBOARD_HTML, 'admin_dashboard.html'))
    changed.append(create_file_safe(root / 'templates/platform_billing/admin_tenant_list.html', ADMIN_TENANT_LIST_HTML, 'admin_tenant_list.html'))
    changed.append(create_file_safe(root / 'templates/platform_billing/admin_tenant_detail.html', ADMIN_TENANT_DETAIL_HTML, 'admin_tenant_detail.html'))
    changed.append(create_file_safe(root / 'templates/platform_billing/admin_revenue.html', ADMIN_REVENUE_HTML, 'admin_revenue.html'))

    print('\n2. apps/platform_billing/models.py — FeatureFlag')
    changed.append(replace_file(root / 'apps/platform_billing/models.py', MODELS_ANCHOR, MODELS_ANCHOR + MODELS_INSERT, MODELS_MARKER, 'FeatureFlag model'))

    print('\n3. apps/core/models.py — Tenant.discount_percent')
    changed.append(replace_file(root / 'apps/core/models.py', CORE_OLD, CORE_NEW, CORE_MARKER, 'discount_percent field'))

    print('\n4. apps/platform_billing/payment_views.py — discount-aware _amount_due')
    changed.append(replace_file(root / 'apps/platform_billing/payment_views.py', AMOUNT_DUE_OLD, AMOUNT_DUE_NEW, AMOUNT_DUE_MARKER, '_amount_due signature'))
    changed.append(replace_file(root / 'apps/platform_billing/payment_views.py', CALL_SITE_1_OLD, CALL_SITE_1_NEW, CALL_SITE_1_MARKER, 'billing_status call site'))
    changed.append(replace_file(root / 'apps/platform_billing/payment_views.py', CALL_SITE_2_OLD, CALL_SITE_2_NEW, CALL_SITE_2_MARKER, 'initiate_platform_payment call site'))

    print('\n5. config/urls.py — platform-admin/ route')
    changed.append(replace_file(root / 'config/urls.py', URLS_ANCHOR, URLS_ANCHOR + URLS_INSERT, URLS_MARKER, 'platform-admin/ include'))

    print(f'\n{"=" * 60}')
    if any(changed):
        print('Patch applied. Next steps:')
        print('  1. python -m py_compile apps/core/models.py apps/platform_billing/*.py')
        print('  2. python manage.py makemigrations core platform_billing')
        print('  3. python manage.py migrate')
        print('  4. python manage.py check')
        print('  5. Set your own user role=platform_admin (or create one) and visit /platform-admin/')
        print('  6. This closes 5A-5F. Worth its own look before going further: the SMS stub from 5D,')
        print('     the per-student overage math several phases have flagged, and the VAT/withholding')
        print('     question from 5E, in roughly that order of how soon they start to matter.')
    else:
        print('Nothing to do — already applied, or something was blocked (see [BLOCKED] above).')


if __name__ == '__main__':
    main()
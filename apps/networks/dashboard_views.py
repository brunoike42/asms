"""
apps/networks/dashboard_views.py

System UI for the Network Admin persona (Section 11) - mirrors
apps/platform_billing/admin_views.py: plain Django views, not DRF,
rendering templates directly against the ORM/service layer
(Appendix E.4 - internal UI doesn't call the public REST API).

Mounted at /network-admin/ in config/urls.py as its own top-level
prefix, same as platform-admin/ - neither persona belongs to a
single tenant, so neither nests under /dashboard/.

Cross-app imports into apps.curriculum are kept local to each
function, same convention networks/views.py and curriculum/views.py
already use for apps.core.Tenant.
"""
import json
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Network, NetworkAdminRole, NetworkDailyMetric
from .services import user_administers_network


def network_admin_required(view_func):
    """@login_required + object-level check against the network in the
    URL, calling user_administers_network() alone - permissions.py's own
    docstring warns this check has drifted from a duplicate once
    already, so there's exactly one place it lives."""
    @wraps(view_func)
    @login_required
    def wrapper(request, network_pk, *args, **kwargs):
        network = get_object_or_404(Network, pk=network_pk)
        if not user_administers_network(request.user, network):
            raise PermissionDenied('Not an active admin of this network.')
        return view_func(request, network, *args, **kwargs)
    return wrapper


@login_required
def network_list(request):
    if request.user.is_staff:
        networks = Network.objects.all().order_by('name')
    else:
        networks = Network.objects.filter(
            admins__user=request.user, admins__is_active=True
        ).order_by('name')

    return render(request, 'networks/dashboard.html', {
        'page_title': 'Networks',
        'networks': networks,
    })


@network_admin_required
def network_schools(request, network):
    schools = network.tenants.all().order_by('name')
    return render(request, 'networks/network_schools.html', {
        'page_title': network.name,
        'network': network,
        'active_tab': 'schools',
        'schools': schools,
    })


@network_admin_required
def network_admins(request, network):
    admins = NetworkAdminRole.objects.filter(network=network).select_related('user').order_by('-invited_at')
    return render(request, 'networks/network_admins.html', {
        'page_title': network.name,
        'network': network,
        'active_tab': 'admins',
        'admins': admins,
    })


@network_admin_required
@require_POST
def network_admin_toggle(request, network, role_pk):
    role = get_object_or_404(NetworkAdminRole, pk=role_pk, network=network)
    role.is_active = not role.is_active
    role.save(update_fields=['is_active'])
    label = role.user.get_full_name() or role.user.email
    messages.success(request, f'{label}: {"activated" if role.is_active else "deactivated"}.')
    return redirect('network_admin:network_admins', network_pk=network.pk)


@network_admin_required
def network_rollups(request, network):
    qs = NetworkDailyMetric.objects.filter(network=network).select_related('tenant')

    metric = request.GET.get('metric', '')
    if metric:
        qs = qs.filter(metric=metric)
    date_from = request.GET.get('date_from', '')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    date_to = request.GET.get('date_to', '')
    if date_to:
        qs = qs.filter(date__lte=date_to)

    available_metrics = list(
        NetworkDailyMetric.objects.filter(network=network)
        .order_by('metric').values_list('metric', flat=True).distinct()
    )

    network_rows = list(qs.filter(tenant__isnull=True).order_by('date'))
    school_rows = list(qs.filter(tenant__isnull=False).order_by('tenant__name', 'date'))

    # Latest value per school for the ranking chart - one pass, since this
    # dataset (schools x days in range) is small and there's no
    # window-function query available at this layer.
    latest_by_school = {}
    for row in school_rows:
        latest_by_school[row.tenant_id] = row  # date-ascending, so last write wins
    ranking = sorted(latest_by_school.values(), key=lambda r: r.value, reverse=True)

    network_latest = network_rows[-1] if network_rows else None
    network_previous = network_rows[-2] if len(network_rows) > 1 else None
    delta = None
    if network_latest and network_previous and network_previous.value:
        delta = round((network_latest.value - network_previous.value) / network_previous.value * 100, 1)

    return render(request, 'networks/network_rollups.html', {
        'page_title': network.name,
        'network': network,
        'active_tab': 'rollups',
        'available_metrics': available_metrics,
        'selected_metric': metric,
        'date_from': date_from,
        'date_to': date_to,
        'network_latest': network_latest,
        'delta': delta,
        'ranking': ranking,
        'ranking_chart_height': max(160, len(ranking) * 32 + 40),
        'sparkline_labels': json.dumps([r.date.isoformat() for r in network_rows]),
        'sparkline_values': json.dumps([float(r.value) for r in network_rows]),
        'ranking_labels': json.dumps([r.tenant.name for r in ranking]),
        'ranking_values': json.dumps([float(r.value) for r in ranking]),
    })


@network_admin_required
def network_curriculum(request, network):
    from apps.curriculum.models import CurriculumAdoption, CurriculumResource

    total_schools = network.tenants.count()
    resources = CurriculumResource.objects.filter(network=network).order_by('-id')
    adoption_counts = dict(
        CurriculumAdoption.objects.filter(resource__network=network)
        .values('resource_id').annotate(n=Count('id')).values_list('resource_id', 'n')
    )

    resource_rows = []
    for r in resources:
        adopted = adoption_counts.get(r.id, 0)
        pct = round(adopted / total_schools * 100) if total_schools else 0
        resource_rows.append({'resource': r, 'adopted': adopted, 'pct': pct})

    return render(request, 'networks/network_curriculum.html', {
        'page_title': network.name,
        'network': network,
        'active_tab': 'curriculum',
        'resource_rows': resource_rows,
        'total_schools': total_schools,
    })


@network_admin_required
@require_POST
def network_curriculum_publish(request, network, resource_pk):
    from apps.curriculum.models import CurriculumResource
    from apps.curriculum.services import publish_resource

    resource = get_object_or_404(CurriculumResource, pk=resource_pk, network=network)
    try:
        resource, synced, skipped = publish_resource(resource, request.user)
    except PermissionDenied as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f'Published version {resource.version}. Synced to {synced} schools, skipped {skipped}.')
    return redirect('network_admin:network_curriculum', network_pk=network.pk)


@network_admin_required
def network_curriculum(request, network):
    from apps.curriculum.models import CurriculumAdoption, CurriculumResource, CurriculumSource, ResourceType

    total_schools = network.tenants.count()
    resources = CurriculumResource.objects.filter(network=network).order_by('-id')
    adoption_counts = dict(
        CurriculumAdoption.objects.filter(resource__network=network)
        .values('resource_id').annotate(n=Count('id')).values_list('resource_id', 'n')
    )

    resource_rows = []
    for r in resources:
        adopted = adoption_counts.get(r.id, 0)
        pct = round(adopted / total_schools * 100) if total_schools else 0
        resource_rows.append({'resource': r, 'adopted': adopted, 'pct': pct})

    return render(request, 'networks/network_curriculum.html', {
        'page_title': network.name,
        'network': network,
        'active_tab': 'curriculum',
        'resource_rows': resource_rows,
        'total_schools': total_schools,
        'resource_type_choices': ResourceType.choices,
        'curriculum_source_choices': CurriculumSource.choices,
    })


@network_admin_required
@require_POST
def network_curriculum_create(request, network):
    from apps.curriculum.models import CurriculumResource, CurriculumSource

    title = request.POST.get('title', '').strip()
    resource_type = request.POST.get('resource_type', '')
    subject = request.POST.get('subject', '').strip()
    level = request.POST.get('level', '').strip()
    content = request.POST.get('content', '').strip()
    curriculum_source = request.POST.get('curriculum_source') or CurriculumSource.NETWORK_CUSTOM
    default_locked = request.POST.get('default_locked') == 'on'
    effective_from_date = request.POST.get('effective_from_date') or None

    if not (title and resource_type and subject and level and content):
        messages.error(request, 'Title, type, subject, level, and content are all required.')
        return redirect('network_admin:network_curriculum', network_pk=network.pk)

    CurriculumResource.objects.create(
        network=network, title=title, resource_type=resource_type, subject=subject,
        level=level, content=content, curriculum_source=curriculum_source,
        default_locked=default_locked, effective_from_date=effective_from_date,
    )
    messages.success(request, f'"{title}" created as a draft. Publish it from the list once ready.')
    return redirect('network_admin:network_curriculum', network_pk=network.pk)


@network_admin_required
@require_POST
def network_admin_add(request, network):
    from apps.accounts.models import User

    email = request.POST.get('email', '').strip()
    if not email:
        messages.error(request, 'Email is required.')
        return redirect('network_admin:network_admins', network_pk=network.pk)

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        messages.error(request, f'No ASMS account found for {email} - they need an account before they can be made a network admin.')
        return redirect('network_admin:network_admins', network_pk=network.pk)

    role, created = NetworkAdminRole.objects.get_or_create(network=network, user=user, defaults={'is_active': True})
    if created:
        messages.success(request, f'{email}: added as network admin.')
    elif not role.is_active:
        role.is_active = True
        role.save(update_fields=['is_active'])
        messages.success(request, f'{email}: reactivated as network admin.')
    else:
        messages.info(request, f'{email} is already an active admin of this network.')
    return redirect('network_admin:network_admins', network_pk=network.pk)
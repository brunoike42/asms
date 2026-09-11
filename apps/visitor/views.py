"""
Visitor Management module views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse

from .models import Visitor, ExpectedVisitor, VisitorLog, VisitorWatchlistEntry
from .forms import (
    VisitorCheckInForm, KnownVisitorCheckInForm,
    ExpectedVisitorForm, VisitorWatchlistEntryForm,
)


def get_tenant(request):
    return getattr(request, 'tenant', None)


def require_visitor_access(view_func):
    """Decorator: only front-desk-capable roles may access visitor management."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if not request.user.can_access_visitor_module():
            messages.error(request, 'You do not have access to Visitor Management.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper

# ─────────────────────────────────────────────
#  Dashboard
# ─────────────────────────────────────────────

@login_required
def dashboard(request):
    tenant = get_tenant(request)
    onsite_visitors = VisitorLog.objects.filter(
        tenant=tenant,
        status__in=[VisitorLog.StatusChoices.CHECKED_IN, VisitorLog.StatusChoices.OVERSTAY],
    ).select_related('visitor', 'host', 'student').order_by('-check_in_time')

    today = timezone.now().date()
    expected_today = ExpectedVisitor.objects.filter(
        tenant=tenant, expected_date=today, status=ExpectedVisitor.StatusChoices.PENDING
    ).order_by('expected_time_from')

    stats = {
        'onsite_count': onsite_visitors.count(),
        'expected_today_count': expected_today.count(),
        'overstay_count': onsite_visitors.filter(status=VisitorLog.StatusChoices.OVERSTAY).count(),
    }

    context = {
        'onsite_visitors': onsite_visitors[:10],
        'expected_today': expected_today[:10],
        'stats': stats,
    }
    return render(request, 'visitor/dashboard.html', context)


# ─────────────────────────────────────────────
#  Check-in flow
# ─────────────────────────────────────────────

@login_required
def checkin(request):
    tenant = get_tenant(request)
    expected = None
    expected_pk = request.GET.get('expected')
    if expected_pk:
        expected = get_object_or_404(ExpectedVisitor, pk=expected_pk, tenant=tenant)

    if request.method == 'POST':
        form = VisitorCheckInForm(request.POST, request.FILES, tenant=tenant)
        if form.is_valid():
            cd = form.cleaned_data
            # Dedup by id_number, per Visitor's own docstring — not by phone,
            # which is only used for the fast-path lookup below.
            if cd['id_number']:
                visitor, _ = Visitor.objects.get_or_create(
                    tenant=tenant, id_number=cd['id_number'],
                    defaults={
                        'full_name': cd['full_name'], 'id_type': cd['id_type'],
                        'phone': cd['phone'], 'photo': cd.get('photo'),
                    },
                )
            else:
                visitor = Visitor.objects.create(
                    tenant=tenant, full_name=cd['full_name'], id_type=cd['id_type'],
                    id_number=cd['id_number'], phone=cd['phone'], photo=cd.get('photo'),
                )

            log = VisitorLog.objects.create(
                tenant=tenant, visitor=visitor, purpose=cd['purpose'],
                host=cd['host'], student=cd['student'],
                items_carried=cd['items_carried'],
                vehicle_registration=cd['vehicle_registration'],
                notes=cd['notes'], signed_in_by=request.user,
                expected_visitor=expected,
            )
            messages.success(request, f'{visitor.full_name} checked in — badge {log.badge_number}.')
            return redirect('visitor:badge_print', pk=log.pk)
    else:
        initial = {}
        if expected:
            initial = {
                'full_name': expected.visitor_name, 'phone': expected.visitor_phone,
                'id_number': expected.visitor_id_number, 'student': expected.student_id,
            }
        form = VisitorCheckInForm(tenant=tenant, initial=initial)

    return render(request, 'visitor/checkin.html', {'form': form, 'expected': expected})


@login_required
def checkin_known(request, visitor_pk):
    tenant = get_tenant(request)
    visitor = get_object_or_404(Visitor, pk=visitor_pk, tenant=tenant)

    if request.method == 'POST':
        form = KnownVisitorCheckInForm(request.POST, tenant=tenant)
        if form.is_valid():
            log = form.save(commit=False)
            log.tenant = tenant
            log.visitor = visitor
            log.signed_in_by = request.user
            log.save()
            messages.success(request, f'{visitor.full_name} checked in — badge {log.badge_number}.')
            return redirect('visitor:badge_print', pk=log.pk)
    else:
        form = KnownVisitorCheckInForm(tenant=tenant)

    return render(request, 'visitor/checkin.html', {'form': form, 'known_visitor': visitor})


@login_required
def visitor_lookup(request):
    """AJAX endpoint — looks up an existing Visitor by phone number."""
    tenant = get_tenant(request)
    phone = request.GET.get('phone', '').strip()
    if not phone:
        return JsonResponse({'found': False})

    visitor = Visitor.objects.filter(tenant=tenant, phone=phone).first()
    if not visitor:
        return JsonResponse({'found': False})

    return JsonResponse({
        'found': True,
        'visitor_id': visitor.pk,
        'full_name': visitor.full_name,
        'is_flagged': visitor.is_flagged,
        'visit_count': visitor.visit_count,
    })


@login_required
def checkout(request, pk):
    tenant = get_tenant(request)
    log = get_object_or_404(VisitorLog, pk=pk, tenant=tenant)
    if request.method == 'POST':
        log.check_out_time = timezone.now()
        log.save()  # save() auto-advances status to CHECKED_OUT
        messages.success(request, f'{log.visitor.full_name} checked out.')
    return redirect('visitor:onsite_list')


@login_required
def badge_print(request, pk):
    tenant = get_tenant(request)
    log = get_object_or_404(VisitorLog, pk=pk, tenant=tenant)
    return render(request, 'visitor/badge.html', {'log': log, 'badge': log.badge_data()})


@login_required
def onsite_list(request):
    tenant = get_tenant(request)
    logs = VisitorLog.objects.filter(
        tenant=tenant,
        status__in=[VisitorLog.StatusChoices.CHECKED_IN, VisitorLog.StatusChoices.OVERSTAY],
    ).select_related('visitor', 'host', 'student').order_by('-check_in_time')
    return render(request, 'visitor/onsite_list.html', {'logs': logs})


# ─────────────────────────────────────────────
#  Pre-registration (expected visitors)
# ─────────────────────────────────────────────

@login_required
def expected_today(request):
    tenant = get_tenant(request)
    today = timezone.now().date()
    expected = ExpectedVisitor.objects.filter(tenant=tenant, expected_date=today).order_by('expected_time_from')
    return render(request, 'visitor/expected_today.html', {'expected': expected})


@login_required
def expected_create(request):
    tenant = get_tenant(request)
    if request.method == 'POST':
        form = ExpectedVisitorForm(request.POST, tenant=tenant)
        if form.is_valid():
            exp = form.save(commit=False)
            exp.tenant = tenant
            exp.registered_by = request.user
            exp.save()
            messages.success(request, f'{exp.visitor_name} pre-registered for {exp.expected_date}.')
            return redirect('visitor:expected_today')
    else:
        form = ExpectedVisitorForm(tenant=tenant)
    return render(request, 'visitor/expected_form.html', {'form': form})


@login_required
def expected_cancel(request, pk):
    tenant = get_tenant(request)
    exp = get_object_or_404(ExpectedVisitor, pk=pk, tenant=tenant)
    if request.method == 'POST':
        exp.status = ExpectedVisitor.StatusChoices.CANCELLED
        exp.save()
        messages.success(request, f'Pre-registration for {exp.visitor_name} cancelled.')
    return redirect('visitor:expected_today')


# ─────────────────────────────────────────────
#  Emergency muster
# ─────────────────────────────────────────────

@login_required
def muster_report(request):
    tenant = get_tenant(request)
    logs = VisitorLog.muster_list(tenant)
    return render(request, 'visitor/muster_report.html', {'logs': logs})


# ─────────────────────────────────────────────
#  Watchlist
# ─────────────────────────────────────────────

@login_required
def watchlist_list(request):
    tenant = get_tenant(request)
    entries = VisitorWatchlistEntry.objects.filter(tenant=tenant).order_by('-is_active', 'full_name')
    return render(request, 'visitor/watchlist_list.html', {'entries': entries})


@login_required
def watchlist_create(request):
    tenant = get_tenant(request)
    if request.method == 'POST':
        form = VisitorWatchlistEntryForm(request.POST, tenant=tenant)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.tenant = tenant
            entry.added_by = request.user
            entry.save()
            messages.success(request, f'{entry.full_name} added to watchlist.')
            return redirect('visitor:watchlist_list')
    else:
        form = VisitorWatchlistEntryForm(tenant=tenant)
    return render(request, 'visitor/watchlist_form.html', {'form': form})


@login_required
def watchlist_deactivate(request, pk):
    tenant = get_tenant(request)
    entry = get_object_or_404(VisitorWatchlistEntry, pk=pk, tenant=tenant)
    if request.method == 'POST':
        entry.is_active = False
        entry.save()
        messages.success(request, f'{entry.full_name} removed from watchlist.')
    return redirect('visitor:watchlist_list')
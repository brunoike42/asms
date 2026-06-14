"""
Discipline module views.

Role access:
- Teacher: can log incidents, view their own reports
- Principal / School Super Admin: full access including approvals
- Counsellor: read-only access to incidents, can see welfare flags
- Accountant, Librarian, etc.: no access
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.core.paginator import Paginator
from django.http import JsonResponse, Http404

from .models import (
    DisciplineIncident, DisciplineConsequence, DisciplineCategory,
    IncidentWitness, IncidentEvidence, MeritRecord, StudentBehaviourSummary
)
from .forms import (
    DisciplineIncidentForm, DisciplineConsequenceForm, ConsequenceApprovalForm,
    IncidentWitnessForm, IncidentEvidenceForm, MeritRecordForm,
    InvestigationNotesForm, PrincipalReviewForm, ParentNotificationForm,
    ResolutionForm, AppealForm, AppealOutcomeForm, DisciplineCategoryForm,
)
from .utils import get_current_term, get_current_academic_year


# ──────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────

STAFF_ROLES = ('teacher', 'principal', 'school_admin', 'super_admin', 'counsellor', 'vice_principal')
MANAGEMENT_ROLES = ('principal', 'school_admin', 'super_admin', 'vice_principal')


def get_tenant(request):
    """Return the current tenant from request context (set by TenantMiddleware)."""
    return getattr(request, 'tenant', None)


def require_discipline_access(view_func):
    """Decorator: only staff roles may access discipline views."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        role = getattr(request.user, 'role', None)
        if role not in STAFF_ROLES and not request.user.is_staff:
            messages.error(request, 'You do not have access to the discipline module.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def require_management(view_func):
    """Decorator: only principal / admin roles for approval actions."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        role = getattr(request.user, 'role', None)
        if role not in MANAGEMENT_ROLES and not request.user.is_staff:
            messages.error(request, 'Only school management can perform this action.')
            return redirect('discipline:dashboard')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ──────────────────────────────────────────────────────────
#  Dashboard
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def dashboard(request):
    tenant = get_tenant(request)
    current_term = get_current_term(tenant)
    current_year = get_current_academic_year(tenant)

    base_qs = DisciplineIncident.objects.filter(tenant=tenant)
    term_qs = base_qs.filter(term=current_term) if current_term else base_qs.none()

    # --- Summary stats ---
    stats = {
        'total_this_term': term_qs.count(),
        'open_incidents': term_qs.filter(status__in=[
            'pending_review', 'under_investigation',
            'awaiting_parent_response', 'awaiting_principal_approval',
        ]).count(),
        'pending_approval': term_qs.filter(status='awaiting_principal_approval').count(),
        'critical_incidents': term_qs.filter(severity='critical').count(),
        'resolved_this_term': term_qs.filter(status__in=['resolved', 'closed']).count(),
        'suspensions': DisciplineConsequence.objects.filter(
            incident__tenant=tenant,
            incident__term=current_term,
            consequence_type__in=['suspension_internal', 'suspension_external'],
            approval_status='completed',
        ).count() if current_term else 0,
        'counselling_flags': term_qs.filter(counselling_flag_raised=True).count(),
        'merits_this_term': MeritRecord.objects.filter(
            tenant=tenant, term=current_term
        ).count() if current_term else 0,
    }

    # --- Recent incidents ---
    recent_incidents = term_qs.select_related(
        'student', 'category', 'reported_by'
    ).order_by('-incident_date', '-report_datetime')[:10]

    # --- Severity breakdown for chart ---
    severity_data = {}
    for s, label in DisciplineIncident.SEVERITY_CHOICES:
        severity_data[label] = term_qs.filter(severity=s).count()

    # --- Category breakdown ---
    category_data = list(
        term_qs.values('category__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:8]
    )

    # --- Top offenders (current term) ---
    top_students = list(
        term_qs.values('student__first_name', 'student__last_name', 'student__id')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    # --- Pending approvals ---
    pending_approvals = term_qs.filter(
        status='awaiting_principal_approval'
    ).select_related('student', 'category')[:5]

    # --- Monthly trend (current year) ---
    from django.db.models.functions import TruncMonth
    monthly_trend = list(
        base_qs.filter(academic_year=current_year)
        .annotate(month=TruncMonth('incident_date'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    context = {
        'page_title': 'Discipline & Behaviour',
        'current_term': current_term,
        'current_year': current_year,
        'stats': stats,
        'recent_incidents': recent_incidents,
        'severity_data': severity_data,
        'category_data': category_data,
        'top_students': top_students,
        'pending_approvals': pending_approvals,
        'monthly_trend': monthly_trend,
        'user_role': getattr(request.user, 'role', ''),
    }
    return render(request, 'discipline/dashboard.html', context)


# ──────────────────────────────────────────────────────────
#  Incident List
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def incident_list(request):
    tenant = get_tenant(request)
    current_term = get_current_term(tenant)

    qs = DisciplineIncident.objects.filter(tenant=tenant).select_related(
        'student', 'category', 'reported_by', 'term'
    ).order_by('-incident_date', '-report_datetime')

    # --- Filters ---
    status_filter = request.GET.get('status', '')
    severity_filter = request.GET.get('severity', '')
    term_filter = request.GET.get('term', '')
    category_filter = request.GET.get('category', '')
    search = request.GET.get('q', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if severity_filter:
        qs = qs.filter(severity=severity_filter)
    if term_filter:
        qs = qs.filter(term_id=term_filter)
    if category_filter:
        qs = qs.filter(category_id=category_filter)
    if search:
        qs = qs.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search) |
            Q(reference_number__icontains=search) |
            Q(title__icontains=search)
        )

    # Teachers only see incidents they reported (unless management)
    role = getattr(request.user, 'role', '')
    if role == 'teacher':
        qs = qs.filter(reported_by=request.user)

    paginator = Paginator(qs, 25)
    page = request.GET.get('page', 1)
    incidents = paginator.get_page(page)

    # For filter dropdowns
    from apps.academics.models import Term
    terms = Term.objects.filter(academic_year__tenant=tenant).select_related('academic_year')
    categories = DisciplineCategory.objects.filter(tenant=tenant, is_active=True)

    context = {
        'page_title': 'Discipline Incidents',
        'incidents': incidents,
        'current_term': current_term,
        'terms': terms,
        'categories': categories,
        'status_choices': DisciplineIncident.STATUS_CHOICES,
        'severity_choices': DisciplineIncident.SEVERITY_CHOICES,
        'filters': {
            'status': status_filter,
            'severity': severity_filter,
            'term': term_filter,
            'category': category_filter,
            'q': search,
        },
        'user_role': role,
    }
    return render(request, 'discipline/incident_list.html', context)


# ──────────────────────────────────────────────────────────
#  Incident Create
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def incident_create(request):
    tenant = get_tenant(request)

    if request.method == 'POST':
        form = DisciplineIncidentForm(request.POST, tenant=tenant)
        if form.is_valid():
            incident = form.save(commit=False)
            incident.tenant = tenant
            incident.reported_by = request.user
            # Auto-set term
            term = get_current_term(tenant)
            if term:
                incident.term = term
                incident.academic_year = term.academic_year
            incident.save()
            form.save_m2m()
            messages.success(
                request,
                f'Incident {incident.reference_number} logged successfully.'
            )
            return redirect('discipline:incident_detail', pk=incident.pk)
    else:
        form = DisciplineIncidentForm(tenant=tenant)

    context = {
        'page_title': 'Log New Incident',
        'form': form,
        'action': 'create',
    }
    return render(request, 'discipline/incident_form.html', context)


# ──────────────────────────────────────────────────────────
#  Incident Detail
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def incident_detail(request, pk):
    tenant = get_tenant(request)
    incident = get_object_or_404(
        DisciplineIncident.objects.select_related(
            'student', 'category', 'reported_by',
            'investigated_by', 'principal_reviewed_by',
            'term', 'academic_year', 'counselling_case',
        ),
        pk=pk, tenant=tenant
    )

    witnesses = incident.witnesses.select_related('witness_student', 'witness_staff')
    consequences = incident.consequences.select_related('assigned_by', 'approved_by')
    evidence = incident.evidence.select_related('uploaded_by')
    co_accused = incident.co_accused_students.all()

    # How many incidents this student has this term
    term_count = 0
    if incident.term:
        from .models import DisciplineIncident as DI
        term_count = DI.objects.filter(
            student=incident.student, term=incident.term, tenant=tenant
        ).count()

    # Forms for inline actions
    consequence_form = DisciplineConsequenceForm()
    witness_form = IncidentWitnessForm(tenant=tenant)
    evidence_form = IncidentEvidenceForm()
    investigation_form = InvestigationNotesForm(instance=incident)
    principal_form = PrincipalReviewForm(instance=incident)
    parent_form = ParentNotificationForm(instance=incident)
    resolution_form = ResolutionForm(instance=incident)
    appeal_form = AppealForm(instance=incident)
    appeal_outcome_form = AppealOutcomeForm(instance=incident)

    context = {
        'page_title': f'Incident {incident.reference_number}',
        'incident': incident,
        'witnesses': witnesses,
        'consequences': consequences,
        'evidence': evidence,
        'co_accused': co_accused,
        'term_count': term_count,
        'consequence_form': consequence_form,
        'witness_form': witness_form,
        'evidence_form': evidence_form,
        'investigation_form': investigation_form,
        'principal_form': principal_form,
        'parent_form': parent_form,
        'resolution_form': resolution_form,
        'appeal_form': appeal_form,
        'appeal_outcome_form': appeal_outcome_form,
        'user_role': getattr(request.user, 'role', ''),
        'can_manage': getattr(request.user, 'role', '') in MANAGEMENT_ROLES or request.user.is_staff,
    }
    return render(request, 'discipline/incident_detail.html', context)


# ──────────────────────────────────────────────────────────
#  Incident Edit
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def incident_edit(request, pk):
    tenant = get_tenant(request)
    incident = get_object_or_404(DisciplineIncident, pk=pk, tenant=tenant)

    # Only reporter or management can edit
    role = getattr(request.user, 'role', '')
    if incident.reported_by != request.user and role not in MANAGEMENT_ROLES and not request.user.is_staff:
        messages.error(request, 'You can only edit incidents you reported.')
        return redirect('discipline:incident_detail', pk=pk)

    if request.method == 'POST':
        form = DisciplineIncidentForm(request.POST, instance=incident, tenant=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, 'Incident updated.')
            return redirect('discipline:incident_detail', pk=pk)
    else:
        form = DisciplineIncidentForm(instance=incident, tenant=tenant)

    context = {
        'page_title': f'Edit Incident {incident.reference_number}',
        'form': form,
        'incident': incident,
        'action': 'edit',
    }
    return render(request, 'discipline/incident_form.html', context)


# ──────────────────────────────────────────────────────────
#  Add Consequence
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def add_consequence(request, pk):
    tenant = get_tenant(request)
    incident = get_object_or_404(DisciplineIncident, pk=pk, tenant=tenant)

    if request.method == 'POST':
        form = DisciplineConsequenceForm(request.POST)
        if form.is_valid():
            consequence = form.save(commit=False)
            consequence.incident = incident
            consequence.assigned_by = request.user

            # Auto-require approval for suspensions/expulsions
            if consequence.consequence_type in ('suspension_internal', 'suspension_external', 'expulsion'):
                consequence.requires_approval = True
                consequence.approval_status = 'pending_approval'
            elif getattr(request.user, 'role', '') in MANAGEMENT_ROLES:
                consequence.approval_status = 'approved'
                consequence.approved_by = request.user
                consequence.approved_at = timezone.now()
            else:
                consequence.requires_approval = True
                consequence.approval_status = 'pending_approval'

            consequence.save()

            # Update incident status
            if consequence.approval_status == 'pending_approval':
                incident.status = 'awaiting_principal_approval'
                incident.requires_principal_approval = True
                incident.save(update_fields=['status', 'requires_principal_approval'])
            else:
                incident.status = 'consequence_applied'
                incident.save(update_fields=['status'])

            messages.success(request, 'Consequence added.')
        else:
            messages.error(request, 'Please correct the form errors.')

    return redirect('discipline:incident_detail', pk=pk)


# ──────────────────────────────────────────────────────────
#  Approve / Reject Consequence
# ──────────────────────────────────────────────────────────

@login_required
@require_management
def approve_consequence(request, pk, consequence_pk):
    tenant = get_tenant(request)
    incident = get_object_or_404(DisciplineIncident, pk=pk, tenant=tenant)
    consequence = get_object_or_404(DisciplineConsequence, pk=consequence_pk, incident=incident)

    if request.method == 'POST':
        action = request.POST.get('action')
        form = ConsequenceApprovalForm(request.POST, instance=consequence)
        if form.is_valid():
            consequence = form.save(commit=False)
            if action == 'approve':
                consequence.approval_status = 'approved'
                incident.principal_reviewed = True
                incident.principal_reviewed_by = request.user
                incident.principal_reviewed_at = timezone.now()
                incident.status = 'consequence_applied'
                messages.success(request, 'Consequence approved.')
            elif action == 'reject':
                consequence.approval_status = 'rejected'
                incident.status = 'under_investigation'
                messages.info(request, 'Consequence rejected. Incident returned for review.')
            consequence.approved_by = request.user
            consequence.approved_at = timezone.now()
            consequence.save()
            incident.save(update_fields=[
                'principal_reviewed', 'principal_reviewed_by',
                'principal_reviewed_at', 'status'
            ])

    return redirect('discipline:incident_detail', pk=pk)


# ──────────────────────────────────────────────────────────
#  Mark Consequence Complete
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def complete_consequence(request, pk, consequence_pk):
    tenant = get_tenant(request)
    incident = get_object_or_404(DisciplineIncident, pk=pk, tenant=tenant)
    consequence = get_object_or_404(DisciplineConsequence, pk=consequence_pk, incident=incident)

    if request.method == 'POST':
        notes = request.POST.get('completion_notes', '')
        consequence.approval_status = 'completed'
        consequence.completed_at = timezone.now()
        consequence.completed_by = request.user
        consequence.completion_notes = notes
        consequence.save()

        # Check if all consequences are done
        pending = incident.consequences.exclude(
            approval_status__in=['completed', 'rejected', 'waived_on_appeal']
        ).count()
        if pending == 0:
            incident.status = 'resolved'
            incident.resolved_at = timezone.now()
            incident.resolved_by = request.user
            incident.save(update_fields=['status', 'resolved_at', 'resolved_by'])
            messages.success(request, 'All consequences completed. Incident marked resolved.')
        else:
            messages.success(request, 'Consequence marked as completed.')

    return redirect('discipline:incident_detail', pk=pk)


# ──────────────────────────────────────────────────────────
#  Add Witness
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def add_witness(request, pk):
    tenant = get_tenant(request)
    incident = get_object_or_404(DisciplineIncident, pk=pk, tenant=tenant)

    if request.method == 'POST':
        form = IncidentWitnessForm(request.POST, tenant=tenant)
        if form.is_valid():
            witness = form.save(commit=False)
            witness.incident = incident
            witness.statement_recorded_by = request.user
            witness.statement_recorded_at = timezone.now()
            witness.save()
            messages.success(request, 'Witness added.')
        else:
            messages.error(request, 'Error adding witness.')

    return redirect('discipline:incident_detail', pk=pk)


# ──────────────────────────────────────────────────────────
#  Add Evidence
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def add_evidence(request, pk):
    tenant = get_tenant(request)
    incident = get_object_or_404(DisciplineIncident, pk=pk, tenant=tenant)

    if request.method == 'POST':
        form = IncidentEvidenceForm(request.POST, request.FILES)
        if form.is_valid():
            evidence = form.save(commit=False)
            evidence.incident = incident
            evidence.uploaded_by = request.user
            evidence.save()
            messages.success(request, 'Evidence uploaded.')
        else:
            messages.error(request, 'Error uploading evidence.')

    return redirect('discipline:incident_detail', pk=pk)


# ──────────────────────────────────────────────────────────
#  Parent Notification
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def mark_parent_notified(request, pk):
    tenant = get_tenant(request)
    incident = get_object_or_404(DisciplineIncident, pk=pk, tenant=tenant)

    if request.method == 'POST':
        form = ParentNotificationForm(request.POST, instance=incident)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.parent_notified = True
            updated.parent_notified_at = timezone.now()
            updated.parent_notified_by = request.user
            updated.save()
            messages.success(request, 'Parent notification recorded.')

    return redirect('discipline:incident_detail', pk=pk)


# ──────────────────────────────────────────────────────────
#  Save Investigation Notes
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def save_investigation(request, pk):
    tenant = get_tenant(request)
    incident = get_object_or_404(DisciplineIncident, pk=pk, tenant=tenant)

    if request.method == 'POST':
        form = InvestigationNotesForm(request.POST, instance=incident)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.status = 'under_investigation'
            updated.investigation_completed_at = timezone.now()
            updated.save()
            messages.success(request, 'Investigation notes saved.')

    return redirect('discipline:incident_detail', pk=pk)


# ──────────────────────────────────────────────────────────
#  Principal Review
# ──────────────────────────────────────────────────────────

@login_required
@require_management
def principal_review(request, pk):
    tenant = get_tenant(request)
    incident = get_object_or_404(DisciplineIncident, pk=pk, tenant=tenant)

    if request.method == 'POST':
        form = PrincipalReviewForm(request.POST, instance=incident)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.principal_reviewed = True
            updated.principal_reviewed_by = request.user
            updated.principal_reviewed_at = timezone.now()
            if incident.status == 'awaiting_principal_approval':
                updated.status = 'consequence_applied'
            updated.save()
            messages.success(request, 'Principal review recorded.')

    return redirect('discipline:incident_detail', pk=pk)


# ──────────────────────────────────────────────────────────
#  Resolve Incident
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def resolve_incident(request, pk):
    tenant = get_tenant(request)
    incident = get_object_or_404(DisciplineIncident, pk=pk, tenant=tenant)

    if request.method == 'POST':
        form = ResolutionForm(request.POST, instance=incident)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.status = 'resolved'
            updated.resolved_at = timezone.now()
            updated.resolved_by = request.user
            updated.save()
            messages.success(request, f'Incident {incident.reference_number} resolved.')

    return redirect('discipline:incident_detail', pk=pk)


# ──────────────────────────────────────────────────────────
#  Appeal Incident
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def appeal_incident(request, pk):
    tenant = get_tenant(request)
    incident = get_object_or_404(DisciplineIncident, pk=pk, tenant=tenant)

    if request.method == 'POST':
        form = AppealForm(request.POST, instance=incident)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.is_appealed = True
            updated.appeal_lodged_at = timezone.now()
            updated.appeal_lodged_by = request.user
            updated.status = 'appealed'
            updated.save()
            messages.info(request, 'Appeal lodged. Awaiting principal review.')

    return redirect('discipline:incident_detail', pk=pk)


@login_required
@require_management
def appeal_outcome(request, pk):
    tenant = get_tenant(request)
    incident = get_object_or_404(DisciplineIncident, pk=pk, tenant=tenant)

    if request.method == 'POST':
        form = AppealOutcomeForm(request.POST, instance=incident)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.appeal_reviewed_by = request.user
            updated.appeal_reviewed_at = timezone.now()
            if updated.appeal_upheld:
                updated.status = 'resolved'
                updated.resolved_at = timezone.now()
                updated.resolved_by = request.user
            else:
                updated.status = 'consequence_applied'
            updated.save()
            messages.success(request, 'Appeal outcome recorded.')

    return redirect('discipline:incident_detail', pk=pk)


# ──────────────────────────────────────────────────────────
#  Student Discipline History
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def student_history(request, student_pk):
    from apps.students.models import Student  # adjust import to your project
    tenant = get_tenant(request)
    student = get_object_or_404(Student, pk=student_pk, tenant=tenant)

    incidents = DisciplineIncident.objects.filter(
        student=student, tenant=tenant
    ).select_related('category', 'term', 'reported_by').order_by('-incident_date')

    merits = MeritRecord.objects.filter(
        student=student, tenant=tenant
    ).select_related('term').order_by('-award_date')

    # Term-by-term summaries
    summaries = StudentBehaviourSummary.objects.filter(
        student=student
    ).select_related('term').order_by('-term__start_date')

    # Stats
    stats = {
        'total_incidents': incidents.count(),
        'open_incidents': incidents.filter(
            status__in=['pending_review', 'under_investigation', 'awaiting_principal_approval']
        ).count(),
        'suspensions': DisciplineConsequence.objects.filter(
            incident__student=student,
            consequence_type__in=['suspension_internal', 'suspension_external'],
            approval_status='completed',
        ).count(),
        'total_merits': merits.aggregate(total=Sum('merit_points'))['total'] or 0,
        'total_demerits': DisciplineConsequence.objects.filter(
            incident__student=student,
            consequence_type='demerit_points',
            approval_status__in=['approved', 'completed'],
        ).aggregate(total=Sum('demerit_points'))['total'] or 0,
    }

    context = {
        'page_title': f'Behaviour Record — {student.first_name} {student.last_name}',
        'student': student,
        'incidents': incidents,
        'merits': merits,
        'summaries': summaries,
        'stats': stats,
        'user_role': getattr(request.user, 'role', ''),
    }
    return render(request, 'discipline/student_history.html', context)


# ──────────────────────────────────────────────────────────
#  Merits
# ──────────────────────────────────────────────────────────

@login_required
@require_discipline_access
def merit_list(request):
    tenant = get_tenant(request)
    current_term = get_current_term(tenant)

    merits = MeritRecord.objects.filter(tenant=tenant).select_related(
        'student', 'awarded_by', 'term'
    ).order_by('-award_date')

    term_filter = request.GET.get('term', '')
    if term_filter:
        merits = merits.filter(term_id=term_filter)
    elif current_term:
        merits = merits.filter(term=current_term)

    paginator = Paginator(merits, 25)
    page = request.GET.get('page', 1)

    from apps.academics.models import Term
    terms = Term.objects.filter(academic_year__tenant=tenant).select_related('academic_year')

    context = {
        'page_title': 'Merit Records',
        'merits': paginator.get_page(page),
        'current_term': current_term,
        'terms': terms,
        'term_filter': term_filter,
    }
    return render(request, 'discipline/merit_list.html', context)


@login_required
@require_discipline_access
def merit_create(request):
    tenant = get_tenant(request)

    if request.method == 'POST':
        form = MeritRecordForm(request.POST, tenant=tenant)
        if form.is_valid():
            merit = form.save(commit=False)
            merit.tenant = tenant
            merit.awarded_by = request.user
            term = get_current_term(tenant)
            year = get_current_academic_year(tenant)
            if term:
                merit.term = term
            if year:
                merit.academic_year = year
            merit.save()
            messages.success(request, f'Merit awarded to {merit.student}.')
            return redirect('discipline:merit_list')
    else:
        form = MeritRecordForm(tenant=tenant)

    context = {
        'page_title': 'Award Merit',
        'form': form,
    }
    return render(request, 'discipline/merit_form.html', context)


# ──────────────────────────────────────────────────────────
#  Category Management
# ──────────────────────────────────────────────────────────

@login_required
@require_management
def category_list(request):
    tenant = get_tenant(request)
    categories = DisciplineCategory.objects.filter(tenant=tenant).order_by('name')
    context = {
        'page_title': 'Discipline Categories',
        'categories': categories,
    }
    return render(request, 'discipline/category_list.html', context)


@login_required
@require_management
def category_create(request):
    tenant = get_tenant(request)
    if request.method == 'POST':
        form = DisciplineCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.tenant = tenant
            category.save()
            messages.success(request, f'Category "{category.name}" created.')
            return redirect('discipline:category_list')
    else:
        form = DisciplineCategoryForm()
    return render(request, 'discipline/category_form.html', {
        'page_title': 'New Discipline Category', 'form': form
    })


@login_required
@require_management
def category_edit(request, pk):
    tenant = get_tenant(request)
    category = get_object_or_404(DisciplineCategory, pk=pk, tenant=tenant)
    if request.method == 'POST':
        form = DisciplineCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated.')
            return redirect('discipline:category_list')
    else:
        form = DisciplineCategoryForm(instance=category)
    return render(request, 'discipline/category_form.html', {
        'page_title': f'Edit Category: {category.name}', 'form': form, 'category': category
    })

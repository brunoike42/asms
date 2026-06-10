from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from .models import AdmissionApplication
from .forms import AdmissionApplicationForm
from apps.core.mixins import require_roles


@login_required
def application_list(request):
    tenant = request.tenant
    status_filter = request.GET.get('status', '')
    qs = AdmissionApplication.objects.filter(tenant=tenant)
    if status_filter:
        qs = qs.filter(status=status_filter)
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))
    status_counts = {
        'submitted':   AdmissionApplication.objects.filter(tenant=tenant, status='submitted').count(),
        'shortlisted': AdmissionApplication.objects.filter(tenant=tenant, status='shortlisted').count(),
        'accepted':    AdmissionApplication.objects.filter(tenant=tenant, status='accepted').count(),
    }
    return render(request, 'admissions/application_list.html', {
        'page_obj': page, 'status_filter': status_filter,
        'status_counts': status_counts,
        'status_choices': AdmissionApplication.StatusChoices.choices,
    })


@login_required
@require_roles('school_admin', 'principal', 'receptionist')
def application_create(request):
    tenant = request.tenant
    form = AdmissionApplicationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        app = form.save(commit=False)
        app.tenant = tenant
        app.save()
        messages.success(request, f'Application {app.application_number} created.')
        return redirect('admissions:detail', pk=app.pk)
    return render(request, 'admissions/application_form.html', {'form': form, 'action': 'New Application'})


@login_required
def application_detail(request, pk):
    app = get_object_or_404(AdmissionApplication, pk=pk, tenant=request.tenant)
    return render(request, 'admissions/application_detail.html', {'application': app})


@login_required
@require_roles('school_admin', 'principal')
def application_edit(request, pk):
    app = get_object_or_404(AdmissionApplication, pk=pk, tenant=request.tenant)
    form = AdmissionApplicationForm(request.POST or None, instance=app)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Application updated.')
        return redirect('admissions:detail', pk=app.pk)
    return render(request, 'admissions/application_form.html', {
        'form': form, 'application': app, 'action': 'Edit Application'
    })

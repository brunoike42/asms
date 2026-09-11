import csv
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404

from apps.core.models import AcademicYear
from .models import EMISSubmission, SchoolInfrastructureRecord
from .forms import EMISExportForm, SchoolInfrastructureRecordForm, SubmissionStatusForm
from .permissions import require_emis_access, get_tenant
from .exporters.registry import get_exporter


@login_required
@require_emis_access
def dashboard(request):
    tenant = get_tenant(request)
    current_year = AcademicYear.objects.filter(tenant=tenant, is_current=True).first()

    issues = []
    if current_year and tenant.emis_country:
        exporter = get_exporter(tenant.emis_country)
        issues = exporter.compliance_issues(tenant)

    infra = None
    if current_year:
        infra = SchoolInfrastructureRecord.objects.filter(
            tenant=tenant, academic_year=current_year
        ).first()

    recent_submissions = EMISSubmission.objects.filter(tenant=tenant)[:10]

    return render(request, "emis/dashboard.html", {
        "tenant": tenant,
        "current_year": current_year,
        "compliance_issues": issues,
        "infra": infra,
        "recent_submissions": recent_submissions,
        "export_form": EMISExportForm(tenant=tenant),
    })


@login_required
@require_emis_access
def run_compliance_check(request):
    tenant = get_tenant(request)
    if not tenant.emis_country:
        messages.error(request, "Set this school's EMIS reporting country first (Django admin).")
        return redirect("emis:dashboard")
    exporter = get_exporter(tenant.emis_country)
    issues = exporter.compliance_issues(tenant)
    return render(request, "emis/compliance_result.html", {
        "issues": issues,
        "template": tenant.get_emis_country_display(),
        "is_clean": not issues,
    })


@login_required
@require_emis_access
def generate_export(request):
    tenant = get_tenant(request)
    if request.method != "POST":
        return redirect("emis:dashboard")

    form = EMISExportForm(request.POST, tenant=tenant)
    if not form.is_valid():
        for error in form.non_field_errors():
            messages.error(request, error)
        for field, errors in form.errors.items():
            for error in errors:
                if field != "__all__":
                    messages.error(request, f"{field}: {error}")
        return redirect("emis:dashboard")

    year = form.cleaned_data["academic_year"]
    template = tenant.emis_country
    exporter = get_exporter(template)
    issues = exporter.compliance_issues(tenant)

    response = HttpResponse(content_type="text/csv")
    filename = f"emis_{template}_{year.name.replace('/', '-')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(exporter.headers)
    for row in exporter.rows(tenant, year):
        writer.writerow(row)

    EMISSubmission.objects.create(
        tenant=tenant,
        academic_year=year,
        country_template=template,
        generated_by=request.user,
        file_path=filename,
        compliance_issues=issues,
        status=EMISSubmission.StatusChoices.GENERATED,
    )

    if issues:
        messages.warning(
            request,
            f"Export generated with {len(issues)} compliance issue(s) — "
            f"resolve these before submitting to the ministry."
        )
    return response


@login_required
@require_emis_access
def submission_list(request):
    tenant = get_tenant(request)
    submissions = EMISSubmission.objects.filter(tenant=tenant)
    return render(request, "emis/submission_list.html", {"submissions": submissions})


@login_required
@require_emis_access
def submission_detail(request, pk):
    tenant = get_tenant(request)
    submission = get_object_or_404(EMISSubmission, pk=pk, tenant=tenant)

    if request.method == "POST":
        form = SubmissionStatusForm(request.POST, instance=submission)
        if form.is_valid():
            updated = form.save(commit=False)
            if updated.status == EMISSubmission.StatusChoices.SUBMITTED and not updated.submitted_by:
                updated.submitted_by = request.user
            updated.save()
            messages.success(request, "Submission record updated.")
            return redirect("emis:submission_detail", pk=pk)
    else:
        form = SubmissionStatusForm(instance=submission)

    return render(request, "emis/submission_detail.html", {
        "submission": submission,
        "form": form,
    })


@login_required
@require_emis_access
def infrastructure_edit(request):
    tenant = get_tenant(request)
    year = AcademicYear.objects.filter(tenant=tenant, is_current=True).first()
    if not year:
        messages.error(request, "Set a current academic year before recording infrastructure data.")
        return redirect("emis:dashboard")

    instance = SchoolInfrastructureRecord.objects.filter(tenant=tenant, academic_year=year).first()
    form = SchoolInfrastructureRecordForm(request.POST or None, instance=instance)

    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.tenant = tenant
        record.academic_year = year
        record.last_updated_by = request.user
        record.save()
        messages.success(request, "Infrastructure record saved.")
        return redirect("emis:dashboard")

    return render(request, "emis/infrastructure_form.html", {"form": form, "year": year})

from django import forms
from apps.core.models import AcademicYear
from .models import EMISSubmission, SchoolInfrastructureRecord


class EMISExportForm(forms.Form):
    """
    country_template is deliberately NOT a form field — it's always
    tenant.emis_country. A school should never be able to generate an
    export in the wrong ministry's format by picking the wrong dropdown
    option.
    """
    academic_year = forms.ModelChoiceField(queryset=AcademicYear.objects.none())

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None:
            self.fields["academic_year"].queryset = AcademicYear.objects.filter(
                tenant=tenant
            ).order_by("-start_date")

    def clean(self):
        cleaned = super().clean()
        if self.tenant and not self.tenant.emis_country:
            raise forms.ValidationError(
                "This school has no EMIS reporting country set. "
                "Set Tenant.emis_country (Django admin) before generating an export."
            )
        return cleaned


class SchoolInfrastructureRecordForm(forms.ModelForm):
    class Meta:
        model = SchoolInfrastructureRecord
        exclude = ["tenant", "created_at", "updated_at", "last_updated_by"]


class SubmissionStatusForm(forms.ModelForm):
    class Meta:
        model = EMISSubmission
        fields = ["status", "submission_reference", "submitted_date", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

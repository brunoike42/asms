from django import forms
from django.utils import timezone
from .models import (
    DisciplineCategory, DisciplineIncident, DisciplineConsequence,
    IncidentWitness, IncidentEvidence, MeritRecord
)


class DisciplineIncidentForm(forms.ModelForm):
    incident_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.now().date
    )
    incident_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'})
    )

    class Meta:
        model = DisciplineIncident
        fields = [
            'student', 'category', 'title', 'description',
            'incident_date', 'incident_time',
            'location', 'location_detail',
            'severity', 'co_accused_students',
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select select2'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief summary of incident'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 5,
                'placeholder': 'Full factual account: what happened, when, who was involved, any immediate actions taken.'
            }),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'location_detail': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Room 4B'}),
            'severity': forms.Select(attrs={'class': 'form-select'}),
            'co_accused_students': forms.SelectMultiple(attrs={'class': 'form-select select2', 'size': 4}),
        }
        labels = {
            'co_accused_students': 'Other Students Involved',
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields['student'].queryset = self.fields['student'].queryset.filter(tenant=tenant)
            self.fields['category'].queryset = DisciplineCategory.objects.filter(tenant=tenant, is_active=True)
            self.fields['co_accused_students'].queryset = self.fields['co_accused_students'].queryset.filter(tenant=tenant)


class InvestigationNotesForm(forms.ModelForm):
    class Meta:
        model = DisciplineIncident
        fields = ['investigation_notes', 'investigated_by']
        widgets = {
            'investigation_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'investigated_by': forms.Select(attrs={'class': 'form-select'}),
        }


class PrincipalReviewForm(forms.ModelForm):
    class Meta:
        model = DisciplineIncident
        fields = ['principal_notes']
        widgets = {
            'principal_notes': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Principal\'s assessment and direction...'
            }),
        }
        labels = {
            'principal_notes': 'Principal\'s Notes / Decision',
        }


class ParentNotificationForm(forms.ModelForm):
    class Meta:
        model = DisciplineIncident
        fields = ['parent_notification_method', 'parent_notification_note']
        widgets = {
            'parent_notification_method': forms.Select(attrs={'class': 'form-select'}),
            'parent_notification_note': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'What was communicated to the parent...'
            }),
        }
        labels = {
            'parent_notification_method': 'How was the parent notified?',
            'parent_notification_note': 'Communication Details',
        }


class ResolutionForm(forms.ModelForm):
    class Meta:
        model = DisciplineIncident
        fields = ['resolution_summary']
        widgets = {
            'resolution_summary': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Summarise how this incident was resolved and the outcome...'
            }),
        }
        labels = {
            'resolution_summary': 'Resolution Summary',
        }


class AppealForm(forms.ModelForm):
    class Meta:
        model = DisciplineIncident
        fields = ['appeal_reason']
        widgets = {
            'appeal_reason': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'State the grounds for this appeal clearly...'
            }),
        }
        labels = {
            'appeal_reason': 'Grounds for Appeal',
        }


class AppealOutcomeForm(forms.ModelForm):
    class Meta:
        model = DisciplineIncident
        fields = ['appeal_outcome', 'appeal_upheld']
        widgets = {
            'appeal_outcome': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'appeal_upheld': forms.NullBooleanSelect(attrs={'class': 'form-select'}),
        }
        labels = {
            'appeal_outcome': 'Appeal Decision & Reasoning',
            'appeal_upheld': 'Was the appeal upheld?',
        }


class DisciplineConsequenceForm(forms.ModelForm):
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = DisciplineConsequence
        fields = [
            'consequence_type', 'description', 'rationale',
            'start_date', 'end_date', 'duration_days', 'schedule_notes',
            'demerit_points', 'restitution_amount', 'restitution_description',
            'requires_approval',
        ]
        widgets = {
            'consequence_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'rationale': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'schedule_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'demerit_points': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'restitution_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'restitution_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'requires_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ConsequenceApprovalForm(forms.ModelForm):
    class Meta:
        model = DisciplineConsequence
        fields = ['approval_notes']
        widgets = {
            'approval_notes': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Principal\'s notes on approval or rejection...'
            }),
        }
        labels = {
            'approval_notes': 'Principal\'s Notes',
        }


class IncidentWitnessForm(forms.ModelForm):
    class Meta:
        model = IncidentWitness
        fields = [
            'witness_type', 'witness_student', 'witness_staff',
            'witness_name', 'witness_contact', 'statement',
        ]
        widgets = {
            'witness_type': forms.Select(attrs={'class': 'form-select'}),
            'witness_student': forms.Select(attrs={'class': 'form-select select2'}),
            'witness_staff': forms.Select(attrs={'class': 'form-select select2'}),
            'witness_name': forms.TextInput(attrs={'class': 'form-control'}),
            'witness_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'statement': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields['witness_student'].queryset = self.fields['witness_student'].queryset.filter(tenant=tenant)
            self.fields['witness_staff'].queryset = self.fields['witness_staff'].queryset.filter(
                profile__tenant=tenant
            ) if hasattr(self.fields['witness_staff'].queryset.model, 'profile') else self.fields['witness_staff'].queryset


class IncidentEvidenceForm(forms.ModelForm):
    class Meta:
        model = IncidentEvidence
        fields = ['evidence_type', 'title', 'description', 'file', 'file_url', 'is_confidential']
        widgets = {
            'evidence_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'file_url': forms.URLInput(attrs={'class': 'form-control'}),
            'is_confidential': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MeritRecordForm(forms.ModelForm):
    award_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.now().date
    )

    class Meta:
        model = MeritRecord
        fields = [
            'student', 'merit_type', 'title', 'description',
            'merit_points', 'award_date',
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select select2'}),
            'merit_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'merit_points': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 50}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields['student'].queryset = self.fields['student'].queryset.filter(tenant=tenant)


class DisciplineCategoryForm(forms.ModelForm):
    class Meta:
        model = DisciplineCategory
        fields = [
            'name', 'code', 'description', 'default_severity',
            'requires_principal_approval', 'triggers_counselling', 'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. FIGHT'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'default_severity': forms.Select(attrs={'class': 'form-select'}),
            'requires_principal_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'triggers_counselling': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

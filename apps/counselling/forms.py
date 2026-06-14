from django import forms
from django.utils import timezone
from .models import (
    WelfareCase, CounsellingSession, WelfareCaseAction,
    BursaryApplication, CounsellorReferral
)


class WelfareCaseForm(forms.ModelForm):
    parent_meeting_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    next_review_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = WelfareCase
        fields = [
            'student', 'case_type', 'title', 'description',
            'priority', 'trigger', 'assigned_counsellor',
            'parent_informed', 'parent_informed_how',
            'parent_meeting_scheduled', 'parent_meeting_date',
            'student_consent_given', 'parent_consent_given',
            'next_review_date',
            'involves_safeguarding', 'involves_abuse', 'involves_self_harm_risk',
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select select2'}),
            'case_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief case title…'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 5,
                'placeholder': 'Describe the situation, presenting concerns, and relevant background…'
            }),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'trigger': forms.Select(attrs={'class': 'form-select'}),
            'assigned_counsellor': forms.Select(attrs={'class': 'form-select select2'}),
            'parent_informed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'parent_informed_how': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Phone call on 12/05'}),
            'parent_meeting_scheduled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'student_consent_given': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'parent_consent_given': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'involves_safeguarding': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'involves_abuse': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'involves_self_harm_risk': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields['student'].queryset = self.fields['student'].queryset.filter(tenant=tenant)
            self.fields['assigned_counsellor'].queryset = self.fields['assigned_counsellor'].queryset.filter(
                role='counsellor'
            ) if hasattr(self.fields['assigned_counsellor'].queryset.model, 'role') else \
                self.fields['assigned_counsellor'].queryset


class CaseUpdateForm(forms.ModelForm):
    next_review_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = WelfareCase
        fields = ['status', 'priority', 'assigned_counsellor', 'next_review_date', 'follow_up_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'assigned_counsellor': forms.Select(attrs={'class': 'form-select'}),
            'follow_up_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class EscalationForm(forms.ModelForm):
    class Meta:
        model = WelfareCase
        fields = ['escalation_reason']
        widgets = {
            'escalation_reason': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Describe why this case needs to be escalated to the principal…'
            }),
        }
        labels = {
            'escalation_reason': 'Reason for Escalation',
        }


class PrincipalResponseForm(forms.ModelForm):
    class Meta:
        model = WelfareCase
        fields = ['principal_response']
        widgets = {
            'principal_response': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Principal\'s guidance, decision, or instructions…'
            }),
        }
        labels = {
            'principal_response': 'Principal\'s Response',
        }


class ResolutionForm(forms.ModelForm):
    class Meta:
        model = WelfareCase
        fields = ['resolution_summary', 'outcome']
        widgets = {
            'resolution_summary': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Describe how this case was resolved and the final outcome…'
            }),
            'outcome': forms.Select(attrs={'class': 'form-select'}),
        }


class CounsellingSessionForm(forms.ModelForm):
    session_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.now().date
    )
    session_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'})
    )
    follow_up_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = CounsellingSession
        fields = [
            'session_date', 'session_time', 'session_type', 'duration_minutes',
            'student_attended', 'parent_attended', 'other_attendees',
            'student_mood', 'mood_notes',
            'session_notes', 'presenting_issues', 'interventions_used',
            'progress_assessment', 'actions_agreed', 'counsellor_actions',
            'follow_up_required', 'follow_up_date', 'urgency_level',
            'risk_reassessment',
            'safeguarding_concern_raised', 'safeguarding_notes',
        ]
        widgets = {
            'session_type': forms.Select(attrs={'class': 'form-select'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 5}),
            'student_attended': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'parent_attended': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'other_attendees': forms.TextInput(attrs={'class': 'form-control'}),
            'student_mood': forms.Select(attrs={'class': 'form-select'}),
            'mood_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'session_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 6,
                'placeholder': 'Confidential session notes — not visible to student, parents, or general staff.'}),
            'presenting_issues': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'interventions_used': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'progress_assessment': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'actions_agreed': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'counsellor_actions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'follow_up_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'urgency_level': forms.Select(attrs={'class': 'form-select'}),
            'risk_reassessment': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'safeguarding_concern_raised': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'safeguarding_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class WelfareCaseActionForm(forms.ModelForm):
    action_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.now().date
    )

    class Meta:
        model = WelfareCaseAction
        fields = ['action_type', 'description', 'action_date', 'outcome', 'outcome_notes']
        widgets = {
            'action_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'outcome': forms.Select(attrs={'class': 'form-select'}),
            'outcome_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class BursaryApplicationForm(forms.ModelForm):
    class Meta:
        model = BursaryApplication
        fields = [
            'waiver_type', 'amount_requested', 'reason',
            'supporting_documents',
            'household_income_estimate', 'number_of_dependants',
            'financial_circumstances',
            'current_fee_balance', 'arrears_days',
        ]
        widgets = {
            'waiver_type': forms.Select(attrs={'class': 'form-select'}),
            'amount_requested': forms.NumberInput(attrs={'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                'placeholder': 'Explain the family\'s circumstances and why relief is needed…'}),
            'supporting_documents': forms.FileInput(attrs={'class': 'form-control'}),
            'household_income_estimate': forms.NumberInput(attrs={'class': 'form-control'}),
            'number_of_dependants': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'financial_circumstances': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'current_fee_balance': forms.NumberInput(attrs={'class': 'form-control'}),
            'arrears_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


class BursaryApprovalForm(forms.ModelForm):
    class Meta:
        model = BursaryApplication
        fields = ['amount_approved', 'approval_notes']
        widgets = {
            'amount_approved': forms.NumberInput(attrs={'class': 'form-control'}),
            'approval_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                'placeholder': 'Principal\'s notes on the approval decision…'}),
        }
        labels = {
            'amount_approved': 'Amount Approved (UGX)',
            'approval_notes': 'Approval Notes',
        }


class CounsellorReferralForm(forms.ModelForm):
    referral_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.now().date
    )
    follow_up_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = CounsellorReferral
        fields = [
            'referral_type', 'referred_to_name', 'referred_to_contact',
            'reason', 'referral_date', 'follow_up_date', 'documents_sent',
        ]
        widgets = {
            'referral_type': forms.Select(attrs={'class': 'form-select'}),
            'referred_to_name': forms.TextInput(attrs={'class': 'form-control'}),
            'referred_to_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'documents_sent': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
